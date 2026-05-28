import streamlit as st
from datetime import datetime, timedelta
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
            return pd.DataFrame(columns=["Nom", "Telephone", "Email", "Date", "Heure", "Prestation"])

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
        col_date = df.columns[3]  # 4ème colonne = Date
        col_heure = df.columns[4]  # 5ème colonne = Heure
        return df[df[col_date] == str(date_rdv)][col_heure].tolist()
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

# --- Gestion des disponibilités ---

def charger_disponibilites():
    try:
        credentials = get_credentials()
        service = build("sheets", "v4", credentials=credentials)
        sheet_id = st.secrets["SHEET_ID"]
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Disponibilites!A:B"
        ).execute()
        valeurs = result.get("values", [])
        jours_bloques = []
        heures_bloquees = []
        jours_debloques = []
        for row in valeurs:
            if len(row) >= 2:
                if row[0] == "jour_bloque":
                    jours_bloques.append(row[1])
                elif row[0] == "heure_bloquee":
                    heures_bloquees.append(row[1])
                elif row[0] == "jour_debloque":
                    jours_debloques.append(row[1])
        return jours_bloques, heures_bloquees, jours_debloques
    except Exception as e:
        st.error(f"Erreur chargement disponibilités : {e}")
        return [], [], []

def sauvegarder_disponibilites(jours_bloques, heures_bloquees, jours_debloques):
    try:
        credentials = get_credentials()
        service = build("sheets", "v4", credentials=credentials)
        sheet_id = st.secrets["SHEET_ID"]
        valeurs = [["type", "valeur"]]
        for j in jours_bloques:
            valeurs.append(["jour_bloque", str(j)])
        for h in heures_bloquees:
            valeurs.append(["heure_bloquee", h])
        for j in jours_debloques:
            valeurs.append(["jour_debloque", str(j)])
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Disponibilites!A:B",
            valueInputOption="RAW",
            body={"values": valeurs}
        ).execute()
        return True
    except Exception as e:
        st.error(f"Erreur sauvegarde disponibilités : {e}")
        return False