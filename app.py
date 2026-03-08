import streamlit as st
import pandas as pd

from backend import (
    load_plantoes,
    save_plantoes,
    load_medicos,
    load_usuarios,
    registrar_log,
)
from auth_module import login, trocar_senha

st.set_page_config(page_title="Plantões UTI", layout="wide")

# ============================
# 1) LOGIN
# ============================

usuario_email = login()
if not usuario_email:
    st.stop()

usuarios_df = load_usuarios()
user_row = usuarios_df[usuarios_df["email"] == usuario_email].iloc[0]

is_admin = bool(user_row.get("admin", False))

st.sidebar.markdown(f"**Logado como:** {usuario_email}")
st.sidebar.markdown(f"**Perfil:** {'Administrador' if is_admin else 'Médico'}")

if st.sidebar.button("Trocar minha senha"):
    trocar_senha(usuario_email)
    st.rerun()

st.title("📋 Sistema de Inscrição de Plantões - UTI")

# ============================
# 2) CARREGAR DADOS
# ============================

plantoes_df = load_plantoes()
medicos_df = load_medicos()

if "nome" not in medicos_df.columns or "email" not in medicos_df.columns:
    st.error("A aba 'medicos' precisa ter as colunas: id, nome, email.")
    st.stop()

# Nome do médico logado
nome_usuario = None
if usuario_email in medicos_df["email"].values:
    nome_usuario = medicos_df.loc[medicos_df["email"] == usuario_email, "nome"].iloc[0]

colunas_candidatos = ["candidato1", "candidato2", "candidato3", "candidato4", "candidato5"]
for col in colunas_candidatos:
    if col not in plantoes_df.columns:
        plantoes_df[col] = ""

# ============================
# 3) ÁREA DO ADMIN
# ============================

if is_admin:
    st.subheader("👑 Área do Administrador")

    st.markdown("""
    Aqui você pode editar **qualquer plantão**, ajustar candidatos,
    corrigir erros e salvar a planilha completa.
    """)

    nomes_medicos = medicos_df["nome"].tolist()

    column_config = {
        col: st.column_config.SelectboxColumn(
            label=col,
            options=[""] + nomes_medicos,
            required=False
        )
        for col in colunas_candidatos
    }

    df_editado = st.data_editor(
        plantoes_df,
        column_config=column_config,
        use_container_width=True,
        key="editor_admin"
    )

    # Verificar duplicidade
    for idx, row in df_editado.iterrows():
        candidatos = [row[col] for col in colunas_candidatos]
        candidatos_limpos = [c for c in candidatos if c not in ["", None]]

        if len(candidatos_limpos) != len(set(candidatos_limpos)):
            st.error(f"⚠️ Linha {idx+1}: o mesmo médico aparece mais de uma vez.")
            st.stop()

    if st.button("Salvar alterações (Administrador)"):
        save_plantoes(df_editado)
        registrar_log(usuario_email, "salvar_planilha", detalhes="Admin atualizou todos os plantões")
        st.success("✔️ Alterações salvas com sucesso! A planilha foi atualizada.")
        st.stop()

    st.subheader("📌 Visualização atual dos plantões")
    st.dataframe(plantoes_df, use_container_width=True)

    # ============================
    # EXPORTAR ESCALA FINAL (ADMIN)
    # ============================

    st.subheader("📤 Exportar escala final")

    st.markdown("""
    Gere um arquivo CSV com todos os plantões e candidatos cadastrados.
    Ideal para auditoria, conferência ou envio para coordenação.
    """)

    if st.button("📥 Baixar escala final (CSV)"):
        df_export = plantoes_df.copy()
        csv = df_export.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Clique aqui para baixar o arquivo",
            data=csv,
            file_name="escala_final.csv",
            mime="text/csv"
        )

        registrar_log(
            usuario_email,
            "exportar_escala",
            detalhes="Administrador exportou a escala final"
        )

        st.success("Arquivo gerado com sucesso!")

# ============================
# 4) ÁREA DO MÉDICO
# ============================

else:
    if not nome_usuario:
        st.error("Seu email não está cadastrado na aba 'medicos'. Fale com o administrador.")
        st.stop()

    st.subheader("🩺 Área do Médico")

    st.markdown("""
    Aqui você pode visualizar todos os plantões disponíveis e se inscrever
    apenas para os horários desejados.  
    Você só pode editar **as suas próprias inscrições**.
    """)

    st.markdown("### 📅 Plantões disponíveis")
    st.dataframe(plantoes_df, use_container_width=True)

    # Criar lista de plantões
    opcoes = []
    for idx, row in plantoes_df.iterrows():
        label = f"{idx} - {row['data']} {row['horario']}"
        opcoes.append((label, idx))

    if not opcoes:
        st.info("Nenhum plantão cadastrado no momento.")
        st.stop()

    labels = [o[0] for o in opcoes]
    escolha = st.selectbox("Selecione um plantão para gerenciar sua inscrição:", labels)
    idx_escolhido = dict(opcoes)[escolha]

    linha = plantoes_df.loc[idx_escolhido]

    st.write("### Detalhes do plantão selecionado")
    st.write(linha[["data", "horario", "vagas"] + colunas_candidatos])

    # ============================
    # INSCRIÇÃO
    # ============================

    if st.button("➕ Inscrever-me neste plantão"):
        candidatos = [linha[col] for col in colunas_candidatos]

        if nome_usuario in candidatos:
            st.warning("Você já está inscrito neste plantão. Não é necessário repetir.")
        else:
            for col in colunas_candidatos:
                if linha[col] in ["", None]:
                    plantoes_df.at[idx_escolhido, col] = nome_usuario
                    save_plantoes(plantoes_df)
                    registrar_log(
                        usuario_email,
                        "inscricao",
                        plantao=f"{linha['data']} {linha['horario']}",
                        detalhes=f"Inscrito como {nome_usuario}"
                    )
                    st.success("✔️ Sua inscrição foi registrada com sucesso!")
                    st.stop()

            st.error("Este plantão já atingiu o número máximo de candidatos.")

    # ============================
    # REMOVER INSCRIÇÃO
    # ============================

    if st.button("❌ Remover minha inscrição deste plantão"):
        candidatos = [linha[col] for col in colunas_candidatos]

        if nome_usuario not in candidatos:
            st.warning("Você não está inscrito neste plantão.")
        else:
            for col in colunas_candidatos:
                if plantoes_df.at[idx_escolhido, col] == nome_usuario:
                    plantoes_df.at[idx_escolhido, col] = ""

            save_plantoes(plantoes_df)
            registrar_log(
                usuario_email,
                "remover_inscricao",
                plantao=f"{linha['data']} {linha['horario']}",
                detalhes=f"Removeu inscrição de {nome_usuario}"
            )
            st.success("✔️ Sua inscrição foi removida.")
            st.stop()

    # ============================
    # MEUS PLANTÕES
    # ============================

    st.markdown("### 📌 Meus plantões")

    mask = plantoes_df[colunas_candidatos].apply(lambda row: nome_usuario in row.values, axis=1)
    meus_plantoes = plantoes_df[mask]

    if meus_plantoes.empty:
        st.info("Você ainda não está inscrito em nenhum plantão.")
    else:
        st.dataframe(meus_plantoes, use_container_width=True)
