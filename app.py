import streamlit as st
import pandas as pd

from backend import load_plantoes, save_plantoes, load_medicos, load_usuarios, registrar_log
from auth_module import login, trocar_senha, logout

st.set_page_config(page_title="Plantões UTI", layout="wide")

COLUNAS_CANDIDATOS = ["candidato1", "candidato2", "candidato3", "candidato4", "candidato5"]


def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def normalizar_nome(valor):
    return normalizar_texto(valor)


def garantir_colunas_candidatos(df):
    df = df.copy()
    for col in COLUNAS_CANDIDATOS:
        if col not in df.columns:
            df[col] = ""
    return df


def linha_para_label(idx, row):
    data = normalizar_texto(row.get("data", ""))
    horario = normalizar_texto(row.get("horario", ""))
    return f"{idx} - {data} {horario}".strip()


def candidatos_da_linha(row):
    candidatos = []
    for col in COLUNAS_CANDIDATOS:
        nome = normalizar_nome(row.get(col, ""))
        if nome:
            candidatos.append(nome)
    return candidatos


def validar_sem_duplicidade(df):
    for idx, row in df.iterrows():
        candidatos = candidatos_da_linha(row)
        if len(candidatos) != len(set(candidatos)):
            raise ValueError(f"Linha {idx + 1}: o mesmo médico aparece mais de uma vez.")


def inscrever_usuario(df, idx_escolhido, nome_usuario):
    df = df.copy()
    linha = df.loc[idx_escolhido]
    candidatos = candidatos_da_linha(linha)

    if nome_usuario in candidatos:
        return False, "Você já está inscrito neste plantão.", df

    for col in COLUNAS_CANDIDATOS:
        if normalizar_nome(linha.get(col, "")) == "":
            df.at[idx_escolhido, col] = nome_usuario
            return True, "✔️ Sua inscrição foi registrada com sucesso!", df

    return False, "Este plantão já atingiu o número máximo de candidatos.", df


def remover_usuario(df, idx_escolhido, nome_usuario):
    df = df.copy()
    linha = df.loc[idx_escolhido]
    candidatos = candidatos_da_linha(linha)

    if nome_usuario not in candidatos:
        return False, "Você não está inscrito neste plantão.", df

    for col in COLUNAS_CANDIDATOS:
        if normalizar_nome(df.at[idx_escolhido, col]) == nome_usuario:
            df.at[idx_escolhido, col] = ""

    return True, "✔️ Sua inscrição foi removida.", df


def tabela_medico(df, nome_usuario):
    base = df.copy()
    base["inscritos"] = base[COLUNAS_CANDIDATOS].apply(lambda row: sum(normalizar_nome(v) != "" for v in row), axis=1)
    base["minha_inscricao"] = base[COLUNAS_CANDIDATOS].apply(lambda row: nome_usuario in [normalizar_nome(v) for v in row], axis=1)
    colunas = [c for c in ["data", "horario", "vagas"] if c in base.columns] + ["inscritos", "minha_inscricao"]
    return base[colunas]


def tabela_meus_plantoes(df, nome_usuario):
    mask = df[COLUNAS_CANDIDATOS].apply(lambda row: nome_usuario in [normalizar_nome(v) for v in row], axis=1)
    return df.loc[mask, [c for c in ["data", "horario", "vagas"] if c in df.columns]]


usuario_email = login()
if not usuario_email:
    st.stop()

usuarios_df = load_usuarios()
usuarios_filtrados = usuarios_df[usuarios_df["email"].astype(str).str.strip().str.lower() == usuario_email.strip().lower()]
if usuarios_filtrados.empty:
    st.error("Usuário autenticado não encontrado na aba 'usuarios'.")
    st.stop()

user_row = usuarios_filtrados.iloc[0]
is_admin = bool(user_row.get("admin", False))
st.session_state["is_admin"] = is_admin

st.sidebar.markdown(f"**Logado como:** {usuario_email}")
st.sidebar.markdown(f"**Perfil:** {'Administrador' if is_admin else 'Médico'}")

if st.sidebar.button("Sair"):
    registrar_log(usuario_email, "logout")
    logout()
    st.rerun()

st.title("📋 Sistema de Inscrição de Plantões - UTI")

with st.expander("Trocar minha senha"):
    trocar_senha(usuario_email)

plantoes_df = garantir_colunas_candidatos(load_plantoes())
medicos_df = load_medicos()

if "nome" not in medicos_df.columns or "email" not in medicos_df.columns:
    st.error("A aba 'medicos' precisa ter as colunas: id, nome, email.")
    st.stop()

match_medico = medicos_df[
    medicos_df["email"].astype(str).str.strip().str.lower() == usuario_email.strip().lower()
]
nome_usuario = None
if not match_medico.empty:
    nome_usuario = normalizar_nome(match_medico.iloc[0]["nome"])

if is_admin:
    st.subheader("👑 Área do Administrador")
    st.markdown("Aqui você pode editar qualquer plantão e também se inscrever como médico.")

    nomes_medicos = sorted({normalizar_nome(n) for n in medicos_df["nome"].tolist() if normalizar_nome(n)})

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
            registrar_log(usuario_email, "salvar_planilha", detalhes="Admin atualizou todos os plantões")
            st.success("✔️ Alterações salvas com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Não foi possível salvar: {e}")

    st.subheader("📌 Visualização atual dos plantões")
    st.dataframe(plantoes_df, use_container_width=True)

    st.subheader("📤 Exportar escala final")
    csv = plantoes_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Baixar escala final (CSV)",
        data=csv,
        file_name="escala_final.csv",
        mime="text/csv",
        on_click=lambda: registrar_log(
            usuario_email,
            "exportar_escala",
            detalhes="Administrador exportou a escala final",
        ),
    )

    st.subheader("🩺 Inscrição como Médico (Admin)")

    if not nome_usuario:
        st.info("Seu email não está cadastrado como médico na aba 'medicos'.")
    else:
        st.dataframe(plantoes_df, use_container_width=True)

        opcoes = [(linha_para_label(idx, row), idx) for idx, row in plantoes_df.iterrows()]
        if opcoes:
            escolha = st.selectbox(
                "Selecione um plantão para gerenciar sua inscrição:",
                [o[0] for o in opcoes],
                key="admin_escolha",
            )
            idx_escolhido = dict(opcoes)[escolha]
            linha = plantoes_df.loc[idx_escolhido]

            st.write("### Detalhes do plantão selecionado")
            st.write(linha[[c for c in ["data", "horario", "vagas"] + COLUNAS_CANDIDATOS if c in linha.index]])

            if st.button("➕ Inscrever-me neste plantão (como médico)", key="admin_inscrever"):
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

            if st.button("❌ Remover minha inscrição deste plantão (como médico)", key="admin_remover"):
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

        st.markdown("### 📌 Meus plantões (como médico)")
        meus_plantoes = tabela_meus_plantoes(plantoes_df, nome_usuario)
        if meus_plantoes.empty:
            st.info("Você ainda não está inscrito em nenhum plantão.")
        else:
            st.dataframe(meus_plantoes, use_container_width=True)

else:
    if not nome_usuario:
        st.error("Seu email não está cadastrado na aba 'medicos'. Fale com o administrador.")
        st.stop()

    st.subheader("🩺 Área do Médico")
    st.markdown("Aqui você pode visualizar os plantões e gerenciar apenas as suas próprias inscrições.")

    st.markdown("### 📅 Plantões disponíveis")
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
