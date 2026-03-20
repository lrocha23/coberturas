import bcrypt
import streamlit as st
from backend import load_usuarios, save_usuarios, registrar_log


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha_digitada: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha_digitada.encode(), senha_hash.encode())


def validar_nova_senha(senha: str):
    senha = senha or ""
    if len(senha) < 10:
        return False, "A senha deve ter pelo menos 10 caracteres."
    return True, ""


def _buscar_usuario_por_email(email: str):
    usuarios = load_usuarios()
    match = usuarios[usuarios["email"].astype(str).str.strip().str.lower() == email.strip().lower()]
    if match.empty:
        return usuarios, None
    return usuarios, match.iloc[0]


def logout():
    for chave in ["usuario", "is_admin"]:
        if chave in st.session_state:
            del st.session_state[chave]


def login():
    st.sidebar.title("Login")

    if st.session_state.get("usuario"):
        return st.session_state["usuario"]

    email = st.sidebar.text_input("Email").strip()
    senha = st.sidebar.text_input("Senha", type="password")

    if st.sidebar.button("Entrar"):
        usuarios, user = _buscar_usuario_por_email(email)

        if user is None:
            st.error("Credenciais inválidas.")
            return None

        if not bool(user.get("ativo", True)):
            st.error("Seu acesso está inativo. Fale com o administrador.")
            registrar_log(email, "login_bloqueado", detalhes="Tentativa com usuário inativo")
            return None

        senha_hash = str(user.get("senha_hash", "") or "").strip()
        if not senha_hash:
            st.error("Sua conta ainda não tem senha configurada. Peça ao administrador para definir uma senha temporária.")
            registrar_log(email, "login_bloqueado", detalhes="Usuário sem senha configurada")
            return None

        try:
            senha_ok = verificar_senha(senha, senha_hash)
        except Exception:
            senha_ok = False

        if not senha_ok:
            st.error("Credenciais inválidas.")
            registrar_log(email, "login_falhou", detalhes="Senha incorreta")
            return None

        st.session_state["usuario"] = str(user["email"]).strip()
        st.session_state["is_admin"] = bool(user.get("admin", False))
        registrar_log(email, "login")
        return st.session_state["usuario"]

    return None


def trocar_senha(email: str):
    st.subheader("🔐 Trocar senha")

    senha_atual = st.text_input("Senha atual", type="password", key="senha_atual")
    nova = st.text_input("Nova senha", type="password", key="trocar_nova_senha")
    confirmar = st.text_input("Confirmar nova senha", type="password", key="trocar_confirmar_senha")

    if st.button("Salvar nova senha"):
        usuarios, user = _buscar_usuario_por_email(email)
        if user is None:
            st.error("Usuário não encontrado.")
            return

        senha_hash = str(user.get("senha_hash", "") or "").strip()
        if not senha_hash or not verificar_senha(senha_atual, senha_hash):
            st.error("A senha atual está incorreta.")
            return

        ok, msg = validar_nova_senha(nova)
        if not ok:
            st.error(msg)
            return

        if nova != confirmar:
            st.error("As senhas não coincidem.")
            return

        usuarios.loc[
            usuarios["email"].astype(str).str.strip().str.lower() == email.strip().lower(),
            "senha_hash"
        ] = hash_senha(nova)

        save_usuarios(usuarios)
        registrar_log(email, "troca_senha", detalhes="Usuário trocou a senha")
        st.success("Senha alterada com sucesso!")
