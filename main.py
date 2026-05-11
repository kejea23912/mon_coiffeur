import streamlit as st
from datetime import date, datetime, timedelta
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Charger les variables du fichier .env
load_dotenv()
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
CALENDAR_ID = os.getenv("CALENDAR_ID")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets"
]

def get_credentials():
    service_account_info = dict(st.secrets["gcp_service_account"])
    return service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )

# --- Google Sheets ---
def sauvegarder_rdv(nom, telephone, email, date_rdv, heure, prestation):
    try:
        credentials = get_credentials()
        service = build("sheets", "v4", credentials=credentials)
        sheet_id = st.secrets["SHEET_ID"]

        valeurs = [[nom, telephone, email, str(date_rdv), heure, prestation]]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="A:F",
            valueInputOption="RAW",
            body={"values": valeurs}
        ).execute()
        return True
    except Exception as e:
        st.error(f"Erreur Google Sheets : {e}")
        return False

def charger_rdv():
    try:
        credentials = get_credentials()
        service = build("sheets", "v4", credentials=credentials)
        sheet_id = st.secrets["SHEET_ID"]

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="A:F"
        ).execute()

        valeurs = result.get("values", [])
        if not valeurs or len(valeurs) < 2:
            return pd.DataFrame(columns=["nom", "telephone", "email", "date", "heure", "prestation"])

        entetes = valeurs[0]
        lignes = valeurs[1:]
        return pd.DataFrame(lignes, columns=entetes)
    except Exception as e:
        st.error(f"Erreur chargement Google Sheets : {e}")
        return pd.DataFrame()

def heures_prises(date_rdv):
    try:
        df = charger_rdv()
        if df.empty:
            return []
        return df[df["date"] == str(date_rdv)]["heure"].tolist()
    except Exception as e:
        st.error(f"Erreur heures prises : {e}")
        return []

# --- Email ---
def envoyer_email(nom, email_client, date_rdv, heure, prestation):
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = email_client
        msg["Subject"] = "✂️ Confirmation de votre rendez-vous"

        corps = f"""
Bonjour {nom},

Votre rendez-vous est confirmé !

📅 Date       : {date_rdv}
🕐 Heure      : {heure}
✂️ Prestation : {prestation}

À bientôt au salon !
        """

        msg.attach(MIMEText(corps, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as serveur:
            serveur.ehlo()
            serveur.starttls()
            serveur.login(GMAIL_USER, GMAIL_PASSWORD)
            serveur.sendmail(GMAIL_USER, email_client, msg.as_string())

        return True
    except Exception as e:
        st.error(f"Erreur email : {e}")
        return False

# --- Google Calendar ---
def ajouter_au_calendar(nom, date_rdv, heure, prestation):
    try:
        credentials = get_credentials()
        service = build("calendar", "v3", credentials=credentials)

        heure_debut = datetime.strptime(f"{date_rdv} {heure}", "%Y-%m-%d %H:%M")
        heure_fin = heure_debut + timedelta(minutes=45)

        evenement = {
            "summary": f"✂️ {prestation} — {nom}",
            "description": f"Client : {nom}\nPrestation : {prestation}",
            "start": {
                "dateTime": heure_debut.isoformat(),
                "timeZone": "Europe/Paris",
            },
            "end": {
                "dateTime": heure_fin.isoformat(),
                "timeZone": "Europe/Paris",
            },
        }

        service.events().insert(calendarId=CALENDAR_ID, body=evenement).execute()
        return True
    except Exception as e:
        st.error(f"Erreur Google Calendar : {e}")
        return False

# --- Interface ---
st.set_page_config(page_title="Mon Salon de Coiffure", page_icon="💈")

page = st.sidebar.selectbox("Navigation", ["📅 Réserver", "📋 Mes rendez-vous"])

if page == "📅 Réserver":
    st.title("💈 Mon Salon de Coiffure")
    st.subheader("Réservez votre rendez-vous")
    st.divider()

    nom = st.text_input("👤 Votre nom et prénom")
    telephone = st.text_input("📱 Votre numéro de téléphone")
    email = st.text_input("📧 Votre email (pour la confirmation)")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        date_rdv = st.date_input("📅 Choisissez une date", min_value=date.today())
    with col2:
        toutes_les_heures = [
            "09:00", "09:45", "10:30", "11:15", "12:00", "12:45", "13:30",
            "14:15", "15:00", "16:00", "16:45", "17:30", "18:15", "19:00",
            "19:45", "20:30", "21:15", "22:00", "22:45"
        ]

    heures_occupees = heures_prises(date_rdv)
    heures_disponibles = [h for h in toutes_les_heures if h not in heures_occupees]

    if heures_disponibles:
        heure_rdv = st.selectbox("🕐 Choisissez une heure", heures_disponibles)
    else:
        st.error("⚠️ Aucune heure disponible pour cette date, choisissez une autre date.")
        st.stop()

    prestation = st.selectbox("✂️ Prestation souhaitée", [
        "Coupe homme", "Coupe + Barbe", "Coupe enfant",
        "Taper ou rafrechisment", "Barbe", "Petite barbe",
    ])

    st.divider()

    if st.button("✅ Confirmer le rendez-vous", use_container_width=True):
        if nom and telephone and email:
            sauvegarder_rdv(nom, telephone, email, date_rdv, heure_rdv, prestation)
            email_envoye = envoyer_email(nom, email, date_rdv, heure_rdv, prestation)
            calendar_ok = ajouter_au_calendar(nom, date_rdv, heure_rdv, prestation)
            st.success(f"Rendez-vous confirmé pour **{nom}** le **{date_rdv}** à **{heure_rdv}** — {prestation}")
            if email_envoye:
                st.info("📧 Email de confirmation envoyé !")
            if calendar_ok:
                st.info("📅 Rendez-vous ajouté à Google Calendar !")
            st.balloons()
        else:
            st.error("⚠️ Veuillez remplir tous les champs !")

elif page == "📋 Mes rendez-vous":
    st.title("📋 Mes rendez-vous")
    st.divider()

    mot_de_passe = st.text_input("🔒 Mot de passe", type="password")

    if mot_de_passe == os.getenv("ADMIN_PASSWORD"):
        df = charger_rdv()
        if df.empty:
            st.info("Aucun rendez-vous pour le moment.")
        else:
            st.dataframe(df, use_container_width=True)
    elif mot_de_passe != "":
        st.error("❌ Mot de passe incorrect !")