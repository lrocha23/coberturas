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
    if data or horario:
        return f"{idx} - {data} {horario}".strip()
    return f"{idx} - Plantão sem data/horário definidos"


def candidatos_da_linha(row):
    candidatos = []
    for col in COLUNAS_CANDIDATOS:
        nome = normalizar_texto(row.get(col, ""))
        if nome:
            candidatos.append(nome)
    return candidatos


def validar_sem_duplicidade(df):
    for idx, row in df.iterrows():
        candidatos = candidatos_da_linha(row)
        if len(candidatos) != len(set(candidatos)):
            raise ValueError(f"Linha {idx + 1}: o mesmo médico aparece mais de uma vez.")


def inscricoes_abertas():
    status = get_config_value("status_inscricoes", "abertas").strip().lower()
    deadline_str = get_config_value("deadline_inscricoes", "").strip()

    abertas_por_status = status != "fechadas"

    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            abertas_por_deadline = agora_sp() <= deadline
        except Exception:
            abertas_por_deadline = True
    else:
        abertas_por_deadline = True

    return abertas_por_status and abertas_por_deadline


def descricao_status_inscricoes():
    status = get_config_value("status_inscricoes", "abertas").strip().lower()
    deadline_str = get_config_value("deadline_inscricoes", "").strip()

    if status == "fechadas":
        return "Fechadas manualmente pelo administrador."

    if deadline_str:
        return f"Abertas até {deadline_str} (horário de São Paulo)."

    return "Abertas sem prazo definido."


def inscrever_usuario(df, idx_escolhido, nome_usuario):
    df = df.copy()
    linha = df.loc[idx_escolhido]
    candidatos = candidatos_da_linha(linha)

    if nome_usuario in candidatos:
        return False, "Você já está inscrito neste plantão.", df

    for col in COLUNAS_CANDIDATOS:
        if normalizar_texto(linha.get(col, "")) == "":
            df.at[idx_escolhido, col] = nome_usuario
            return True, "✔️ Sua inscrição foi registrada com sucesso!", df

    return False, "Este plantão já atingiu o número máximo de candidatos.", df


def remover_usuario(df, idx_escolhido, nome_usuario):
    df = df.copy()
    estava_inscrito = False
    for col in COLUNAS_CANDIDATOS:
        if normalizar_texto(df.at[idx_escolhido, col]) == nome_usuario:
            df.at[idx_escolhido, col] = ""
            estava_inscrito = True
    if not estava_inscrito:
        return False, "Você não está inscrito neste plantão.", df
    return True, "✔️ Sua inscrição foi removida.", df


def tabela_medico(df, nome_usuario):
    base = df.copy()
    base["inscritos"] = base[COLUNAS_CANDIDATOS].apply(
        lambda row: sum(normalizar_texto(v) != "" for v in row), axis=1
    )
    base["minha_inscricao"] = base[COLUNAS_CANDIDATOS].apply(
        lambda row: nome_usuario in [normalizar_texto(v) for v in row], axis=1
    )
    colunas = [c for c in ["data", "horario", "vagas"] if c in base.columns] + ["inscritos", "minha_inscricao"]
    return base[colunas]


def tabela_meus_plantoes(df, nome_usuario):
    mask = df[COLUNAS_CANDIDATOS].apply(
        lambda row: nome_usuario in [normalizar_texto(v) for v in row], axis=1
    )
    return df.loc[mask, [c for c in ["data", "horario", "vagas"] if c in df.columns]]


# =========================
# LOGIN
# =========================

usuario_email = login()
if not usuario_email:
    st.stop()

usuarios_df = load_usuarios()
user_row = usuarios_df[
    usuarios_df["email"].str.strip().str.lower() == usuario_email.strip().lower()
].iloc[0]

is_admin = bool(user_row.get("admin", False))

# Nome do médico
medicos_df = load_medicos()

match_medico = medicos_df[
    medicos_df["email"].astype(str).str.strip().str.lower()
    == usuario_email.strip().lower()
]

if not match_medico.empty:
    nome_usuario = normalizar_texto(match_medico.iloc[0]["nome"])
    saudacao_login = f"Dr. {nome_usuario}"
else:
    nome_usuario = ""
    saudacao_login = "Dr."

# Toast só uma vez
if not st.session_state.get("toast_login_exibido", False):
    st.toast(f"Login realizado com sucesso, {saudacao_login}!", icon="✅")
    st.session_state["toast_login_exibido"] = True

# Esconder sidebar
st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# =========================
# HEADER
# =========================

col1, col2 = st.columns([6, 1])

with col1:
    st.title("📋 Sistema de Inscrição de Plantões - UTI")
    st.caption(f"Logado como: {saudacao_login} | Perfil: {'Administrador' if is_admin else 'Médico'}")

with col2:
    if st.button("Sair"):
        registrar_log(usuario_email, "logout")
        logout()
        st.session_state.clear()
        st.rerun()

with st.expander("Trocar minha senha"):
    trocar_senha(usuario_email)

# =========================
# APP
# =========================

plantoes_df = garantir_colunas_candidatos(load_plantoes())

status_texto = descricao_status_inscricoes()
if inscricoes_abertas():
    st.info(f"🟢 Inscrições abertas. {status_texto}")
else:
    st.warning(f"🔴 Inscrições fechadas. {status_texto}")

# -------------------------
# ADMIN
# -------------------------

if is_admin:
    abas = st.tabs(["Editar plantões", "Controle da rodada", "Gerar escala"])

    with abas[0]:
        st.subheader("Editar plantões")

        df_editado = st.data_editor(plantoes_df, use_container_width=True)

        if st.button("Salvar alterações"):
            save_plantoes(df_editado)
            st.success("Salvo!")

    with abas[1]:
        if st.button("Abrir inscrições"):
            set_config_value("status_inscricoes", "abertas")

        if st.button("Fechar inscrições"):
            set_config_value("status_inscricoes", "fechadas")

    with abas[2]:
        if st.button("Gerar escala"):
            resultado_df, historico = generate_scale_from_df(plantoes_df)
            save_resultado_escala(resultado_df)
            save_historico_mes_atual(historico)
            st.success("Escala gerada!")

# -------------------------
# MÉDICO
# -------------------------

else:
    st.subheader("Área do Médico")
    st.dataframe(tabela_medico(plantoes_df, nome_usuario))