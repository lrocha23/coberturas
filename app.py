import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

from backend import (
    load_plantoes,
    save_plantoes,
    load_medicos,
    load_usuarios,
    load_historico_mes_passado,
    save_resultado_escala,
    save_historico_mes_atual,
    save_snapshot_plantoes,
    registrar_log,
    get_config_value,
    set_config_value,
)
from auth_module import login, trocar_senha, logout
from selection_module import generate_scale_from_df

st.set_page_config(page_title="Plantões UTI", layout="wide")

COLUNAS_CANDIDATOS = ["candidato1", "candidato2", "candidato3", "candidato4", "candidato5"]
TZ = pytz.timezone("America/Sao_Paulo")


def agora_sp():
    return datetime.now(TZ)


def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def garantir_colunas_candidatos(df):
    df = df.copy()
    for col in COLUNAS_CANDIDATOS:
        if col not in df.columns:
            df[col] = ""
    return df


def linha_para_label(idx, row):
    data = normalizar_texto(row.get("data", ""))
    horario = normalizar_texto(row.get("horario", ""))
    return f"{idx} - {data} {horario}"


def candidatos_da_linha(row):
    return [normalizar_texto(row.get(col, "")) for col in COLUNAS_CANDIDATOS if normalizar_texto(row.get(col, ""))]


def validar_sem_duplicidade(df):
    for idx, row in df.iterrows():
        candidatos = candidatos_da_linha(row)
        if len(candidatos) != len(set(candidatos)):
            raise ValueError(f"Linha {idx + 1}: médico duplicado.")


def inscricoes_abertas():
    status = get_config_value("status_inscricoes", "abertas").lower()
    deadline_str = get_config_value("deadline_inscricoes", "")

    if status == "fechadas":
        return False

    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            return agora_sp() <= deadline
        except:
            return True

    return True


def descricao_status_inscricoes():
    status = get_config_value("status_inscricoes", "abertas").lower()
    deadline_str = get_config_value("deadline_inscricoes", "")

    if status == "fechadas":
        return "Fechadas manualmente."

    if deadline_str:
        return f"Abertas até {deadline_str}"

    return "Abertas"


def inscrever_usuario(df, idx, nome):
    df = df.copy()
    row = df.loc[idx]

    if nome in candidatos_da_linha(row):
        return False, "Já inscrito.", df

    for col in COLUNAS_CANDIDATOS:
        if not normalizar_texto(row[col]):
            df.at[idx, col] = nome
            return True, "Inscrito!", df

    return False, "Sem vagas.", df


def remover_usuario(df, idx, nome):
    df = df.copy()
    for col in COLUNAS_CANDIDATOS:
        if df.at[idx, col] == nome:
            df.at[idx, col] = ""
            return True, "Removido!", df
    return False, "Não estava inscrito.", df


# =========================
# LOGIN
# =========================

usuario_email = login()
if not usuario_email:
    st.stop()

usuarios_df = load_usuarios()
user_row = usuarios_df[usuarios_df["email"].str.lower() == usuario_email.lower()].iloc[0]
is_admin = bool(user_row.get("admin", False))

medicos_df = load_medicos()

match = medicos_df[medicos_df["email"].str.lower() == usuario_email.lower()]

if not match.empty:
    nome_usuario = normalizar_texto(match.iloc[0]["nome"])
    saudacao = f"Dr. {nome_usuario}"
else:
    nome_usuario = ""
    saudacao = "Dr."

# Toast
if not st.session_state.get("toast_login", False):
    st.toast(f"Login realizado com sucesso, {saudacao}!", icon="✅")
    st.session_state["toast_login"] = True

# Esconder sidebar
st.markdown("""<style>[data-testid="stSidebar"] {display:none;}</style>""", unsafe_allow_html=True)

# =========================
# HEADER
# =========================

col1, col2 = st.columns([6, 1])

with col1:
    st.title("📋 Sistema de Plantões UTI")
    st.caption(f"{saudacao} | {'Admin' if is_admin else 'Médico'}")

with col2:
    if st.button("Sair"):
        logout()
        st.session_state.clear()
        st.rerun()

with st.expander("Trocar senha"):
    trocar_senha(usuario_email)

# =========================
# APP
# =========================

plantoes_df = garantir_colunas_candidatos(load_plantoes())

if is_admin:
    abas = st.tabs(["Editar", "Rodada", "Escala", "Minha inscrição"])

    with abas[0]:
        df_edit = st.data_editor(plantoes_df)
        if st.button("Salvar"):
            validar_sem_duplicidade(df_edit)
            save_plantoes(df_edit)
            st.success("Salvo!")

    with abas[1]:
        if st.button("Abrir"):
            set_config_value("status_inscricoes", "abertas")
        if st.button("Fechar"):
            set_config_value("status_inscricoes", "fechadas")

    with abas[2]:
        if st.button("Gerar escala"):
            res, hist = generate_scale_from_df(plantoes_df)
            save_resultado_escala(res)
            save_historico_mes_atual(hist)
            st.success("Gerado!")

    with abas[3]:
        idx = st.selectbox("Plantão", plantoes_df.index)
        if st.button("Inscrever"):
            ok, msg, df = inscrever_usuario(plantoes_df, idx, nome_usuario)
            if ok:
                save_plantoes(df)
                st.success(msg)
                st.rerun()

else:
    st.dataframe(plantoes_df)