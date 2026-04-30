import streamlit as st
from datetime import date, datetime, timedelta
import sqlite3
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

# --- Base de données ---
def init_db():
    conn = sqlite3.connect("reservations.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            telephone TEXT,
            email TEXT,
            date TEXT,
            heure TEXT,
            prestation TEXT
        )
    """)
    conn.commit()
    conn.close()

def sauvegarder_rdv(nom, telephone, email, date_rdv, heure, prestation):
    conn = sqlite3.connect("reservations.db")
    conn.execute("""
        INSERT INTO reservations (nom, telephone, email, date, heure, prestation)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nom, telephone, email, str(date_rdv), heure, prestation))
    conn.commit()
    conn.close()

def charger_rdv():
    conn = sqlite3.connect("reservations.db")
    df = pd.read_sql("SELECT * FROM reservations ORDER BY date, heure", conn)
    conn.close()
    return df

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
        credentials = service_account.Credentials.from_service_account_file(
            "credentials.json",
            scopes=["https://www.googleapis.com/auth/calendar"]
        )

        service = build("calendar", "v3", credentials=credentials)

        # Construire la date et heure de début et fin
        heure_debut = datetime.strptime(f"{date_rdv} {heure}", "%Y-%m-%d %H:%M")
        heure_fin = heure_debut + timedelta(minutes=30)

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

# Initialiser la base de données
init_db()

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
        heure_rdv = st.selectbox("🕐 Choisissez une heure", [
            "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
            "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00"
        ])

    prestation = st.selectbox("✂️ Prestation souhaitée", [
        "Coupe homme", "Coupe femme", "Coupe enfant",
        "Coupe + barbe", "Coloration",
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
    df = charger_rdv()
    if df.empty:
        st.info("Aucun rendez-vous pour le moment.")
    else:
        st.dataframe(df, use_container_width=True)