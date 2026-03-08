import bcrypt
import streamlit as st
import pandas as pd
from backend import load_usuarios, save_usuarios, registrar_log

# ============================
# 1) Hash de senha
# ============================

def hash_senha(senha):
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

def verificar_senha(senha_digitada, senha_hash):
    return bcrypt.checkpw(senha_digitada.encode(), senha_hash.encode())

# ============================
# 2) Login com fluxo de primeiro acesso
# ============================

def login():
    st.sidebar.title("Login")

    # Inicializa estado
    if "login_step" not in st.session_state:
        st.session_state.login_step = "login"   # login → first_access → done
    if "pending_email" not in st.session_state:
        st.session_state.pending_email = None

    # ============================
    # ETAPA 1 — LOGIN NORMAL
    # ============================
    if st.session_state.login_step == "login":
        email = st.sidebar.text_input("Email")
        senha = st.sidebar.text_input("Senha", type="password")

        if st.sidebar.button("Entrar"):
            usuarios = load_usuarios()

            if email not in usuarios["email"].values:
                st.error("Email não encontrado.")
                return None

            user = usuarios[usuarios["email"] == email].iloc[0]

            # Primeiro acesso
            if user["senha_hash"] == "" or pd.isna(user["senha_hash"]):
                st.session_state.login_step = "first_access"
                st.session_state.pending_email = email
                st.rerun()   # <--- CORRIGIDO

            # Login normal
            if not verificar_senha(senha, user["senha_hash"]):
                st.error("Senha incorreta.")
                return None

            registrar_log(email, "login")
            st.session_state["usuario"] = email
            return email

        return st.session_state.get("usuario", None)

    # ============================
    # ETAPA 2 — PRIMEIRO ACESSO
    # ============================
    if st.session_state.login_step == "first_access":
        st.warning("Parece que este é seu primeiro acesso. Crie uma nova senha.")

        nova = st.text_input("Nova senha", type="password", key="nova_senha")
        confirmar = st.text_input("Confirmar nova senha", type="password", key="confirmar_senha")

        if st.button("Salvar nova senha"):
            if nova != confirmar:
                st.error("As senhas não coincidem.")
                return None

            usuarios = load_usuarios()
            usuarios.loc[usuarios["email"] == st.session_state.pending_email, "senha_hash"] = hash_senha(nova)
            save_usuarios(usuarios)

            registrar_log(st.session_state.pending_email, "primeiro_acesso", detalhes="Criou senha inicial")

            st.success("Senha criada com sucesso! Faça login novamente.")

            # Reset do fluxo
            st.session_state.login_step = "login"
            st.session_state.pending_email = None
            st.session_state["usuario"] = None
            st.rerun()   # <--- CORRIGIDO

        return None

# ============================
# 3) Trocar senha
# ============================

def trocar_senha(email):
    st.title("Trocar senha")

    nova = st.text_input("Nova senha", type="password", key="trocar_nova_senha")
    confirmar = st.text_input("Confirmar nova senha", type="password", key="trocar_confirmar_senha")

    if st.button("Salvar nova senha"):
        if nova != confirmar:
            st.error("As senhas não coincidem.")
            return

        usuarios = load_usuarios()
        usuarios.loc[usuarios["email"] == email, "senha_hash"] = hash_senha(nova)
        save_usuarios(usuarios)

        registrar_log(email, "troca_senha", detalhes="Usuário trocou a senha")

        st.success("Senha alterada com sucesso!")