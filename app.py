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
usuarios_filtrados = usuarios_df[
    usuarios_df["email"].astype(str).str.strip().str.lower() == usuario_email.strip().lower()
]
if usuarios_filtrados.empty:
    st.error("Usuário autenticado não encontrado na aba 'usuarios'.")
    st.stop()

user_row = usuarios_filtrados.iloc[0]
is_admin = bool(user_row.get("admin", False))
st.session_state["is_admin"] = is_admin

medicos_df = load_medicos()

if "nome" not in medicos_df.columns or "email" not in medicos_df.columns:
    st.error("A aba 'medicos' precisa ter as colunas: id, nome, email.")
    st.stop()

match_medico = medicos_df[
    medicos_df["email"].astype(str).str.strip().str.lower() == usuario_email.strip().lower()
]

if not match_medico.empty:
    nome_usuario = normalizar_texto(match_medico.iloc[0]["nome"])
    saudacao_login = f"Dr. {nome_usuario}"
else:
    nome_usuario = ""
    saudacao_login = "Dr."

st.session_state["nome_usuario"] = nome_usuario

if not st.session_state.get("toast_login_exibido", False):
    st.toast(f"Login realizado com sucesso, {saudacao_login}!", icon="✅")
    st.session_state["toast_login_exibido"] = True

# Esconde a sidebar depois do login
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# =========================
# CABEÇALHO
# =========================

col_info, col_logout = st.columns([5, 1])

with col_info:
    st.title("📋 Sistema de Inscrição de Plantões - UTI")
    st.caption(f"Logado como: {saudacao_login} | Perfil: {'Administrador' if is_admin else 'Médico'}")

with col_logout:
    st.write("")
    st.write("")
    if st.button("Sair"):
        registrar_log(usuario_email, "logout")
        logout()
        st.session_state.pop("toast_login_exibido", None)
        st.session_state.pop("nome_usuario", None)
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

if is_admin:
    abas = st.tabs(["Editar plantões", "Controle da rodada", "Gerar escala", "Minha inscrição (como médico)"])

    with abas[0]:
        st.subheader("👑 Editar plantões")
        st.markdown(
            "A aba **plantoes** precisa ter estas colunas: "
            "`data`, `horario`, `vagas`, `candidato1` ... `candidato5`."
        )

        nomes_medicos = sorted({normalizar_texto(n) for n in medicos_df["nome"].tolist() if normalizar_texto(n)})

        column_config = {
            col: st.column_config.SelectboxColumn(
                label=col,
                options=[""] + nomes_medicos,
                required=False,
            )
            for col in COLUNAS_CANDIDATOS
        }

        df_editado = st.data_editor(
            plantoes_df,
            column_config=column_config,
            use_container_width=True,
            key="editor_admin",
        )

        if st.button("Salvar alterações (Administrador)"):
            try:
                validar_sem_duplicidade(df_editado)
                save_plantoes(df_editado)
                registrar_log(usuario_email, "salvar_planilha", detalhes="Admin atualizou os plantões")
                st.success("✔️ Alterações salvas com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Não foi possível salvar: {e}")

        st.dataframe(plantoes_df, use_container_width=True)

    with abas[1]:
        st.subheader("🧭 Controle da rodada")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Status atual**")
            st.write(status_texto)

            if st.button("Abrir inscrições"):
                set_config_value("status_inscricoes", "abertas")
                registrar_log(usuario_email, "abrir_inscricoes", detalhes="Admin abriu as inscrições")
                st.success("Inscrições abertas.")
                st.rerun()

            if st.button("Fechar inscrições"):
                set_config_value("status_inscricoes", "fechadas")
                registrar_log(usuario_email, "fechar_inscricoes", detalhes="Admin fechou as inscrições")
                st.success("Inscrições fechadas.")
                st.rerun()

        with col2:
            st.markdown("**Prazo automático**")
            deadline_atual = get_config_value("deadline_inscricoes", "")
            novo_deadline = st.text_input(
                "Deadline (formato YYYY-MM-DD HH:MM)",
                value=deadline_atual,
                help="Exemplo: 2026-03-25 18:00",
            )

            if st.button("Salvar deadline"):
                set_config_value("deadline_inscricoes", novo_deadline.strip())
                registrar_log(usuario_email, "definir_deadline", detalhes=f"Deadline definido: {novo_deadline.strip()}")
                st.success("Deadline salvo.")
                st.rerun()

            if st.button("Remover deadline"):
                set_config_value("deadline_inscricoes", "")
                registrar_log(usuario_email, "remover_deadline", detalhes="Deadline removido")
                st.success("Deadline removido.")
                st.rerun()

        st.markdown("---")
        st.markdown("**Snapshot da rodada**")
        st.caption("Cria uma cópia da aba 'plantoes' em 'plantoes_fechado' antes da geração da escala.")

        if st.button("Salvar snapshot de plantoes_fechado"):
            try:
                save_snapshot_plantoes(plantoes_df)
                registrar_log(usuario_email, "snapshot_plantoes", detalhes="Snapshot salvo em plantoes_fechado")
                st.success("Snapshot salvo com sucesso em 'plantoes_fechado'.")
            except Exception as e:
                st.error(f"Não foi possível salvar o snapshot: {e}")

    with abas[2]:
        st.subheader("⚙️ Gerar escala")
        st.markdown("Gera a seleção automaticamente a partir das candidaturas registradas.")
        seed = st.number_input("Seed do sorteio", min_value=1, value=42, step=1)
        historico_df = load_historico_mes_passado()

        if st.button("Gerar snapshot + fechar inscrições + gerar escala"):
            try:
                save_snapshot_plantoes(plantoes_df)
                set_config_value("status_inscricoes", "fechadas")

                resultado_df, historico_atual_df = generate_scale_from_df(
                    plantoes_df=plantoes_df,
                    historico_df=historico_df,
                    seed=int(seed),
                )

                save_resultado_escala(resultado_df)
                save_historico_mes_atual(historico_atual_df)
                registrar_log(
                    usuario_email,
                    "gerar_escala",
                    detalhes=f"Escala gerada automaticamente com seed={int(seed)}; inscrições fechadas; snapshot salvo",
                )

                st.success(
                    "Escala gerada. Snapshot salvo em 'plantoes_fechado', inscrições fechadas, "
                    "resultado salvo em 'resultado_escala' e histórico em 'historico_mes_atual'."
                )
                st.dataframe(resultado_df, use_container_width=True)

                csv = resultado_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Baixar resultado da escala (CSV)",
                    data=csv,
                    file_name="resultado_escala.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.error(f"Não foi possível gerar a escala: {e}")

    with abas[3]:
        st.subheader("🩺 Minha inscrição (como médico)")
        if not nome_usuario:
            st.info("Seu email não está cadastrado como médico na aba 'medicos'.")
        else:
            opcoes = [(linha_para_label(idx, row), idx) for idx, row in plantoes_df.iterrows()]
            if opcoes:
                escolha = st.selectbox("Selecione um plantão:", [o[0] for o in opcoes], key="admin_escolha")
                idx_escolhido = dict(opcoes)[escolha]
                linha = plantoes_df.loc[idx_escolhido]

                st.write(linha[[c for c in ["data", "horario", "vagas"] + COLUNAS_CANDIDATOS if c in linha.index]])

                if st.button("➕ Inscrever-me", key="admin_inscrever"):
                    if not inscricoes_abertas():
                        st.warning("As inscrições estão fechadas.")
                    else:
                        ok, msg, novo_df = inscrever_usuario(plantoes_df, idx_escolhido, nome_usuario)
                        if ok:
                            save_plantoes(novo_df)
                            registrar_log(
                                usuario_email,
                                "inscricao_admin",
                                plantao=f"{linha.get('data', '')} {linha.get('horario', '')}",
                                detalhes=f"Admin inscrito como {nome_usuario}",
                            )
                            st.success(msg)
                            st.rerun()
                        else:
                            st.warning(msg)

                if st.button("❌ Remover minha inscrição", key="admin_remover"):
                    if not inscricoes_abertas():
                        st.warning("As inscrições estão fechadas.")
                    else:
                        ok, msg, novo_df = remover_usuario(plantoes_df, idx_escolhido, nome_usuario)
                        if ok:
                            save_plantoes(novo_df)
                            registrar_log(
                                usuario_email,
                                "remover_inscricao_admin",
                                plantao=f"{linha.get('data', '')} {linha.get('horario', '')}",
                                detalhes=f"Admin removeu inscrição de {nome_usuario}",
                            )
                            st.success(msg)
                            st.rerun()
                        else:
                            st.warning(msg)
else:
    if not nome_usuario:
        st.error("Seu email não está cadastrado na aba 'medicos'. Fale com o administrador.")
        st.stop()

    st.subheader("🩺 Área do Médico")
    st.dataframe(tabela_medico(plantoes_df, nome_usuario), use_container_width=True)

    opcoes = [(linha_para_label(idx, row), idx) for idx, row in plantoes_df.iterrows()]
    if not opcoes:
        st.info("Nenhum plantão cadastrado no momento.")
        st.stop()

    escolha = st.selectbox("Selecione um plantão para gerenciar sua inscrição:", [o[0] for o in opcoes])
    idx_escolhido = dict(opcoes)[escolha]
    linha = plantoes_df.loc[idx_escolhido]

    st.write("### Detalhes do plantão selecionado")
    st.write(linha[[c for c in ["data", "horario", "vagas"] if c in linha.index]])

    if st.button("➕ Inscrever-me neste plantão"):
        if not inscricoes_abertas():
            st.warning("As inscrições estão fechadas.")
        else:
            ok, msg, novo_df = inscrever_usuario(plantoes_df, idx_escolhido, nome_usuario)
            if ok:
                save_plantoes(novo_df)
                registrar_log(
                    usuario_email,
                    "inscricao",
                    plantao=f"{linha.get('data', '')} {linha.get('horario', '')}",
                    detalhes=f"Inscrito como {nome_usuario}",
                )
                st.success(msg)
                st.rerun()
            else:
                st.warning(msg)

    if st.button("❌ Remover minha inscrição deste plantão"):
        if not inscricoes_abertas():
            st.warning("As inscrições estão fechadas.")
        else:
            ok, msg, novo_df = remover_usuario(plantoes_df, idx_escolhido, nome_usuario)
            if ok:
                save_plantoes(novo_df)
                registrar_log(
                    usuario_email,
                    "remover_inscricao",
                    plantao=f"{linha.get('data', '')} {linha.get('horario', '')}",
                    detalhes=f"Removeu inscrição de {nome_usuario}",
                )
                st.success(msg)
                st.rerun()
            else:
                st.warning(msg)

    st.markdown("### 📌 Meus plantões")
    meus_plantoes = tabela_meus_plantoes(plantoes_df, nome_usuario)
    if meus_plantoes.empty:
        st.info("Você ainda não está inscrito em nenhum plantão.")
    else:
        st.dataframe(meus_plantoes, use_container_width=True)