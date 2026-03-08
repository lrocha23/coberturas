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
# 2) Login
# ============================

def login():
    st.sidebar.title("Login")

    email = st.sidebar.text_input("Email")
    senha = st.sidebar.text_input("Senha", type="password")

    if st.sidebar.button("Entrar"):
        usuarios = load_usuarios()

        if email not in usuarios["email"].values:
            st.error("Email não encontrado.")
            return None

        user = usuarios[usuarios["email"] == email].iloc[0]

        if not verificar_senha(senha, user["senha_hash"]):
            st.error("Senha incorreta.")
            return None

        registrar_log(email, "login")
        st.session_state["usuario"] = email
        return email

    return st.session_state.get("usuario", None)

# ============================
# 3) Troca de senha
# ============================

def trocar_senha(email):
    st.subheader("Trocar senha")

    nova = st.text_input("Nova senha", type="password")
    confirmar = st.text_input("Confirmar senha", type="password")

    if st.button("Salvar nova senha"):
        if nova != confirmar:
            st.error("As senhas não coincidem.")
            return

        usuarios = load_usuarios()
        usuarios.loc[usuarios["email"] == email, "senha_hash"] = hash_senha(nova)
        save_usuarios(usuarios)

        registrar_log(email, "troca_senha")
        st.success("Senha alterada com sucesso!")