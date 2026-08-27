"""
Montagem da remessa — a pasta que o coordenador anexa ao e-mail da PRF.

Uma pasta por sessao (RN-14), contendo:

    CONTRAMAO_20260825_v1/
        CONTRAMAO_NDU8490_340201LFF....pdf
        CONTRAMAO_RQI2E47_340201LFF....pdf
        indice.csv
        remessa.zip

Gerar de novo nao sobrescreve: cria v2 ao lado da v1 (RN-15).
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import zipfile
from datetime import datetime

from . import laudo
from . import parametros as P
from .dominio import Relatorio


def proxima_pasta(modulo: str, quando: datetime | None = None) -> str:
    """A primeira versao que ainda nao existe em disco (RN-15)."""
    base = P.pasta_remessas()
    data = (quando or datetime.now()).strftime("%Y%m%d")
    prefixo = P.MODULOS[modulo]["prefixo_arquivo"]
    versao = 1
    while True:
        nome = P.MOLDE_PASTA_REMESSA.format(modulo=prefixo, data=data,
                                            versao=versao)
        alvo = os.path.join(base, nome)
        if not os.path.isdir(alvo):
            return alvo
        versao += 1


def ja_e_remessa(pasta: str) -> bool:
    """Uma pasta que ja tem indice.csv e uma remessa gerada."""
    return os.path.isfile(os.path.join(pasta, P.NOME_INDICE))


def gravar_indice(rel: Relatorio, modulo: str, pasta: str,
                  gerados: list[str]) -> str:
    """RF-47 — um registro por laudo."""
    caminho = os.path.join(pasta, P.NOME_INDICE)
    por_nome = {os.path.basename(g): g for g in gerados}

    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["arquivo", "id_transito", "data", "hora", "praca", "pista",
                    "faixa", "placa", "categoria", "velocidade", "fotos",
                    "paginas", "operador", "decidido_em"])
        for t in rel.autuados:
            nome = t.nome_laudo(modulo)
            if nome not in por_nome:
                continue
            w.writerow([
                nome, t.id, t.data, t.hora, t.praca, t.pista,
                t.campo("faixa"), t.placa, t.categoria, t.velocidade,
                " ".join(t.selecao_ordenada()), t.paginas_laudo,
                t.decidido_por, t.decidido_em,
            ])
    return caminho


def compactar(pasta: str) -> str:
    """RF-50 — a remessa vira um anexo so."""
    caminho = os.path.join(pasta, P.NOME_ZIP)
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in sorted(os.listdir(pasta)):
            if nome == P.NOME_ZIP:
                continue
            alvo = os.path.join(pasta, nome)
            if os.path.isfile(alvo):
                z.write(alvo, arcname=nome)
    return caminho


def gerar(rel: Relatorio, modulo: str, pasta: str | None = None,
          progresso=None) -> dict:
    """
    Gera os relatorios, o indice e o zip. Falha em um nao interrompe os
    demais (RNF-10).
    """
    autuados = rel.autuados
    if not autuados:
        raise ValueError("Nenhum trânsito autuado para gerar.")

    destino = pasta or proxima_pasta(modulo)

    # RN-15 — nada e sobrescrito. Se a pasta pedida ja e uma remessa gerada,
    # a nova vai para a versao seguinte, ao lado. A regra mora aqui e nao na
    # tela de proposito: assim vale para qualquer chamada.
    nova_versao = False
    if os.path.isdir(destino) and ja_e_remessa(destino):
        destino = proxima_pasta(modulo)
        nova_versao = True

    try:
        os.makedirs(destino, exist_ok=True)
    except OSError as e:
        raise ValueError(f"Não consegui criar a pasta: {e}") from e

    gerados, falhas = laudo.gerar_todos(rel, modulo, destino, progresso)
    indice = gravar_indice(rel, modulo, destino, gerados)
    zip_caminho = compactar(destino)

    return {
        "pasta": destino,
        "nova_versao": nova_versao,
        "relatorios": len(gerados),
        "arquivos": [os.path.basename(g) for g in gerados],
        "indice": os.path.basename(indice),
        "zip": os.path.basename(zip_caminho),
        "tamanho_zip": os.path.getsize(zip_caminho),
        "fotos": sum(len(t.selecao_ordenada()) for t in autuados),
        "paginas": sum(t.paginas_laudo for t in autuados),
        "falhas": falhas,
    }


def abrir_no_explorador(pasta: str) -> None:
    """RF-49."""
    if not pasta or not os.path.isdir(pasta):
        raise ValueError("Pasta não encontrada.")
    if sys.platform.startswith("win"):
        os.startfile(pasta)                                   # type: ignore
    elif sys.platform == "darwin":
        subprocess.Popen(["open", pasta])
    else:
        subprocess.Popen(["xdg-open", pasta])
