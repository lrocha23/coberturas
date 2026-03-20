import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import pytz

SPREADSHEET_ID_FALLBACK = "1H91D58YS8bpohvxzmqBwaOMk2SvI2p7bx8B8Nnp-G5Y"


@st.cache_resource
def get_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


@st.cache_resource
def get_sheet():
    spreadsheet_id = st.secrets.get("spreadsheet_id", SPREADSHEET_ID_FALLBACK)
    return get_client().open_by_key(spreadsheet_id)


def _normalize_bool_series(series):
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "sim"])
    )


def _load_worksheet_df(worksheet_name: str) -> pd.DataFrame:
    ws = get_sheet().worksheet(worksheet_name)
    data = ws.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        values = ws.get_all_values()
        if values:
            header = values[0]
            df = pd.DataFrame(columns=header)

    return df


@st.cache_data(ttl=15)
def load_plantoes():
    df = _load_worksheet_df("plantoes")
    for col in ["candidato1", "candidato2", "candidato3", "candidato4", "candidato5"]:
        if col not in df.columns:
            df[col] = ""
    return df


@st.cache_data(ttl=60)
def load_medicos():
    return _load_worksheet_df("medicos")


@st.cache_data(ttl=15)
def load_usuarios():
    df = _load_worksheet_df("usuarios")
    df["admin"] = _normalize_bool_series(df["admin"]) if "admin" in df.columns else False
    df["ativo"] = _normalize_bool_series(df["ativo"]) if "ativo" in df.columns else True
    return df


@st.cache_data(ttl=30)
def load_historico_mes_passado():
    try:
        return _load_worksheet_df("historico_mes_passado")
    except Exception:
        return pd.DataFrame(columns=["nome", "plantoes", "horas"])


@st.cache_data(ttl=10)
def load_config():
    try:
        df = _load_worksheet_df("config")
        if df.empty:
            return pd.DataFrame(columns=["chave", "valor"])
        return df
    except Exception:
        return pd.DataFrame(columns=["chave", "valor"])


def _get_or_create_worksheet(worksheet_name: str, rows: int = 200, cols: int = 20):
    sh = get_sheet()
    try:
        return sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=worksheet_name, rows=rows, cols=cols)


def _save_dataframe_to_worksheet(worksheet_name: str, df: pd.DataFrame):
    ws = _get_or_create_worksheet(worksheet_name)

    df_to_save = df.fillna("").copy()
    values = [df_to_save.columns.tolist()] + df_to_save.astype(str).values.tolist()

    rows_needed = max(len(values), 1)
    cols_needed = max((len(r) for r in values), default=1)

    current_rows = ws.row_count
    current_cols = ws.col_count

    if current_rows < rows_needed or current_cols < cols_needed:
        ws.resize(rows=max(current_rows, rows_needed), cols=max(current_cols, cols_needed))

    ws.update("A1", values)

    if current_rows > rows_needed:
        ws.batch_clear([f"A{rows_needed + 1}:{gspread.utils.rowcol_to_a1(current_rows, max(current_cols, cols_needed))}"])
    elif current_cols > cols_needed:
        start = gspread.utils.rowcol_to_a1(1, cols_needed + 1)
        end = gspread.utils.rowcol_to_a1(rows_needed, current_cols)
        ws.batch_clear([f"{start}:{end}"])

    load_plantoes.clear()
    load_medicos.clear()
    load_usuarios.clear()
    load_historico_mes_passado.clear()
    load_config.clear()


def save_plantoes(df: pd.DataFrame):
    _save_dataframe_to_worksheet("plantoes", df)


def save_usuarios(df: pd.DataFrame):
    _save_dataframe_to_worksheet("usuarios", df)


def save_resultado_escala(df: pd.DataFrame):
    _save_dataframe_to_worksheet("resultado_escala", df)


def save_historico_mes_atual(df: pd.DataFrame):
    _save_dataframe_to_worksheet("historico_mes_atual", df)


def save_snapshot_plantoes(df: pd.DataFrame):
    _save_dataframe_to_worksheet("plantoes_fechado", df)


def save_config(df: pd.DataFrame):
    _save_dataframe_to_worksheet("config", df)


def get_config_value(chave: str, default: str = "") -> str:
    df = load_config()
    if df.empty or "chave" not in df.columns or "valor" not in df.columns:
        return default

    match = df[df["chave"].astype(str).str.strip().str.lower() == chave.strip().lower()]
    if match.empty:
        return default
    return str(match.iloc[0]["valor"]).strip()


def set_config_value(chave: str, valor: str):
    df = load_config()
    if df.empty:
        df = pd.DataFrame(columns=["chave", "valor"])

    if "chave" not in df.columns:
        df["chave"] = ""
    if "valor" not in df.columns:
        df["valor"] = ""

    mask = df["chave"].astype(str).str.strip().str.lower() == chave.strip().lower()
    if mask.any():
        df.loc[mask, "valor"] = str(valor)
    else:
        df = pd.concat([df, pd.DataFrame([{"chave": chave, "valor": str(valor)}])], ignore_index=True)

    save_config(df)


def registrar_log(usuario, acao, plantao="", detalhes=""):
    ws = _get_or_create_worksheet("logs", rows=500, cols=10)

    tz = pytz.timezone("America/Sao_Paulo")
    timestamp = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    existing = ws.get("A1:E1")
    if not existing:
        ws.update("A1", [["timestamp", "usuario", "acao", "plantao", "detalhes"]])

    ws.append_row([timestamp, usuario, acao, plantao, detalhes], value_input_option="USER_ENTERED")
