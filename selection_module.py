import random
import pandas as pd

COLUNAS_CANDIDATOS = ["candidato1", "candidato2", "candidato3", "candidato4", "candidato5"]

PESO_ATUAL = 1.0
PESO_MES_PASSADO = 0.5
PESO_ANO = 0.2

MAPA_HORAS = {
    "07:30-13:30": 6,
    "13:30-19:30": 6,
    "19:30-07:30": 12,
}


def _normalizar(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def _horas_do_plantao(horario):
    horario = _normalizar(horario)
    if horario not in MAPA_HORAS:
        raise ValueError(
            f"Horário inválido: {horario}. Valores aceitos: {', '.join(MAPA_HORAS.keys())}"
        )
    return MAPA_HORAS[horario]


def _ordenar_plantoes(df):
    df = df.copy()
    if "data" not in df.columns or "horario" not in df.columns:
        return df

    ordem_horarios = {
        "07:30-13:30": 1,
        "13:30-19:30": 2,
        "19:30-07:30": 3,
    }
    df["_ord_data"] = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
    df["_ord_horario"] = df["horario"].astype(str).str.strip().map(ordem_horarios).fillna(99)
    return df.sort_values(["_ord_data", "_ord_horario"], kind="stable").reset_index(drop=True)


def _get_candidatos(row):
    candidatos = []
    for col in COLUNAS_CANDIDATOS:
        nome = _normalizar(row.get(col, ""))
        if nome:
            candidatos.append(nome)
    return list(dict.fromkeys(candidatos))


def _validar_plantoes(df):
    obrigatorias = ["data", "horario", "vagas"] + COLUNAS_CANDIDATOS
    faltantes = [c for c in obrigatorias if c not in df.columns]
    if faltantes:
        raise ValueError(
            "A aba 'plantoes' precisa ter as colunas: "
            + ", ".join(obrigatorias)
            + f". Faltando: {', '.join(faltantes)}"
        )

    df = df.copy()
    df["vagas"] = pd.to_numeric(df["vagas"], errors="coerce")
    if df["vagas"].isna().any():
        raise ValueError("Há valores inválidos em 'vagas'.")
    df["vagas"] = df["vagas"].astype(int)

    for _, row in df.iterrows():
        _horas_do_plantao(row["horario"])

    return df


def generate_scale_from_df(plantoes_df: pd.DataFrame, historico_df: pd.DataFrame | None = None, seed: int = 42):
    random.seed(seed)

    df_original = plantoes_df.copy()
    df_original["_ordem_original"] = range(len(df_original))

    df = _validar_plantoes(df_original)
    df = _ordenar_plantoes(df)

    historico_df = historico_df.copy() if historico_df is not None else pd.DataFrame(columns=["nome", "plantoes", "horas"])
    if historico_df.empty:
        historico_mes_passado = {}
        horas_mes_passado = {}
    else:
        historico_df["nome"] = historico_df["nome"].astype(str).str.strip()
        historico_df["plantoes"] = pd.to_numeric(historico_df["plantoes"], errors="coerce").fillna(0).astype(int)
        historico_df["horas"] = pd.to_numeric(historico_df["horas"], errors="coerce").fillna(0).astype(int)
        historico_mes_passado = dict(zip(historico_df["nome"], historico_df["plantoes"]))
        horas_mes_passado = dict(zip(historico_df["nome"], historico_df["horas"]))

    historico_ano = {}

    ganhos_rodada = {}
    horas_rodada = {}
    escolhas = []
    logs_escolha = []

    def calcular_carga(nome):
        return (
            PESO_ATUAL * ganhos_rodada.get(nome, 0)
            + PESO_MES_PASSADO * historico_mes_passado.get(nome, 0)
            + PESO_ANO * historico_ano.get(nome, 0)
        )

    for _, row in df.iterrows():
        candidatos = _get_candidatos(row)
        vagas = int(row["vagas"])
        horas_plantao = _horas_do_plantao(row["horario"])

        if not candidatos or vagas == 0:
            escolhas.append([])
            logs_escolha.append("Sem candidatos ou sem vagas")
            continue

        if len(candidatos) <= vagas:
            escolhidos = candidatos.copy()
            for nome in escolhidos:
                ganhos_rodada[nome] = ganhos_rodada.get(nome, 0) + 1
                horas_rodada[nome] = horas_rodada.get(nome, 0) + horas_plantao

            escolhas.append(escolhidos)
            logs_escolha.append("Camada 1: candidatos <= vagas")
            continue

        disponiveis = candidatos.copy()
        escolhidos = []
        motivos_vaga = []

        for numero_vaga in range(1, vagas + 1):
            cargas = {nome: calcular_carga(nome) for nome in disponiveis}
            menor_carga = min(cargas.values())
            empatados = [n for n, c in cargas.items() if c == menor_carga]

            motivo = [
                f"Vaga {numero_vaga}",
                f"Camada 2: menor carga={menor_carga}",
                f"empatados={empatados}",
            ]

            sem_plantao_no_mes = [n for n in empatados if ganhos_rodada.get(n, 0) == 0]
            if sem_plantao_no_mes:
                empatados = sem_plantao_no_mes
                motivo.append(f"Camada 2.5: priorizou sem plantão no mês={empatados}")

            if len(empatados) > 1:
                horas_totais = {
                    nome: horas_mes_passado.get(nome, 0) + horas_rodada.get(nome, 0)
                    for nome in empatados
                }
                menor_horas = min(horas_totais.values())
                empatados = [n for n, h in horas_totais.items() if h == menor_horas]
                motivo.append(f"Camada 3: menor horas={menor_horas}, empatados finais={empatados}")

            escolhido = random.choice(empatados)
            motivo.append(f"Camada 4: sorteio escolheu={escolhido}")

            escolhidos.append(escolhido)
            disponiveis.remove(escolhido)
            ganhos_rodada[escolhido] = ganhos_rodada.get(escolhido, 0) + 1
            horas_rodada[escolhido] = horas_rodada.get(escolhido, 0) + horas_plantao

            motivos_vaga.append(" | ".join(motivo))

        escolhas.append(escolhidos)
        logs_escolha.append(" || ".join(motivos_vaga))

    df["plantonistas_escolhidos"] = [", ".join(e) for e in escolhas]
    df["log_escolha"] = logs_escolha

    resultado_df = df.sort_values("_ordem_original", kind="stable").drop(
        columns=[c for c in ["_ordem_original", "_ord_data", "_ord_horario"] if c in df.columns],
        errors="ignore",
    )

    historico_atual_df = pd.DataFrame(
        [
            {"nome": nome, "plantoes": ganhos_rodada.get(nome, 0), "horas": horas_rodada.get(nome, 0)}
            for nome in sorted(set(list(ganhos_rodada.keys()) + list(horas_rodada.keys())))
        ]
    )

    return resultado_df, historico_atual_df
