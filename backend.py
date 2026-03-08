import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# ============================
# 1) Conexão com Google Sheets
# ============================

def get_client():
    creds_dict = st.secrets["gcp_service_account"]

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes
    )

    client = gspread.Client(auth=creds)
    client.session = gspread.auth.HTTPClient(creds)

    return client

def get_sheet():
    client = get_client()
    # ABRE A PLANILHA PELO ID — 100% confiável
    return client.open_by_key("1H91D58YS8bpohvxzmqBwaOMk2SvI2p7bx8B8Nnp-G5Y")

# ============================
# 2) Funções de leitura
# ============================

def load_plantoes():
    ws = get_sheet().worksheet("plantoes")
    data = ws.get_all_records()
    return pd.DataFrame(data)

def load_medicos():
    ws = get_sheet().worksheet("medicos")
    data = ws.get_all_records()
    return pd.DataFrame(data)

def load_usuarios():
    ws = get_sheet().worksheet("usuarios")
    data = ws.get_all_records()
    return pd.DataFrame(data)

# ============================
# 3) Funções de escrita
# ============================

def save_plantoes(df):
    ws = get_sheet().worksheet("plantoes")
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

def save_usuarios(df):
    ws = get_sheet().worksheet("usuarios")
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

# ============================
# 4) Logs
# ============================

def registrar_log(usuario, acao, plantao="", detalhes=""):
    ws = get_sheet().worksheet("logs")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([timestamp, usuario, acao, plantao, detalhes])