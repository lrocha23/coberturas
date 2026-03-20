import bcrypt
import streamlit as st
from backend import load_usuarios, save_usuarios, registrar_log


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha_digitada: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha_digitada.encode(), senha_hash.encode())


def validar_nova_senha(senha: str):
    senha = senha or ""
    if len(senha) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."
    return True, ""


def _buscar_usuario_por_email(email: str):
    usuarios = load_usuarios()
    match = usuarios[usuarios["email"].astype(str).str.strip().str.lower() == email.strip().lower()]
    if match.empty:
        return usuarios, None
    return usuarios, match.iloc[0]


def logout():
    for chave in ["usuario", "is_admin"]:
        st.session_state.pop(chave, None)


def _fluxo_primeiro_acesso(email: str, usuarios, user):
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Primeiro acesso**")
    chave_primeiro_acesso = st.sidebar.text_input("Chave de primeiro acesso", type="password", key="primeiro_acesso_chave")
    nova = st.sidebar.text_input("Crie sua senha", type="password", key="primeiro_nova")
    confirmar = st.sidebar.text_input("Confirme sua senha", type="password", key="primeiro_confirma")

    if st.sidebar.button("Ativar conta"):
        chave_correta = st.secrets.get("first_access_key", "")

        if not chave_correta:
            st.error("A chave de primeiro acesso não está configurada no app.")
            return None

        if chave_primeiro_acesso != chave_correta:
            st.error("Chave de primeiro acesso inválida.")
            registrar_log(email, "primeiro_acesso_falhou", detalhes="Chave global incorreta")
            return None

        ok, msg = validar_nova_senha(nova)
        if not ok:
            st.error(msg)
            return None

        if nova != confirmar:
            st.error("As senhas não coincidem.")
            return None

        usuarios.loc[
            usuarios["email"].astype(str).str.strip().str.lower() == email.strip().lower(),
            "senha_hash"
        ] = hash_senha(nova)

        save_usuarios(usuarios)

        st.session_state["usuario"] = str(user["email"]).strip()
        st.session_state["is_admin"] = bool(user.get("admin", False))

        registrar_log(email, "primeiro_acesso_ok", detalhes="Senha criada no primeiro acesso")
        st.success("Conta ativada com sucesso!")
        st.rerun()

    return None


def login():
    st.sidebar.title("Login")

    if st.session_state.get("usuario"):
        return st.session_state["usuario"]

    email = st.sidebar.text_input("Email").strip()
    senha = st.sidebar.text_input("Senha", type="password")

    usuarios, user = _buscar_usuario_por_email(email) if email else (None, None)

    if user is not None and not bool(user.get("ativo", True)):
        st.sidebar.error("Seu acesso está inativo.")
        return None

    if user is not None:
        senha_hash = str(user.get("senha_hash", "") or "").strip()
        if not senha_hash:
            return _fluxo_primeiro_acesso(email, usuarios, user)

    if st.sidebar.button("Entrar"):
        if user is None:
            st.error("Credenciais inválidas.")
            return None

        senha_hash = str(user.get("senha_hash", "") or "").strip()
        if not senha_hash:
            st.error("Você precisa concluir o primeiro acesso antes de entrar.")
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
