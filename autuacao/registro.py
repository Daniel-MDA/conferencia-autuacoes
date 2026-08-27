"""
Registro em arquivo (RNF-16).

Empacotado, a aplicacao roda sem console: se algo falha na partida — a janela
nativa que nao abre, a planilha que nao le, o laudo que nao sai — nao ha para
onde a mensagem ir. Este modulo da um lugar.

O arquivo fica ao lado do executavel quando da, e na pasta temporaria quando
nao da (pasta de programas sem permissao de escrita, por exemplo).
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler

from . import parametros as P

NOME = "ConferenciaAutuacoes.log"
_pronto = False


def caminho() -> str:
    ao_lado = os.path.join(P.pasta_do_executavel(), NOME)
    try:
        with open(ao_lado, "a", encoding="utf-8"):
            pass
        return ao_lado
    except OSError:
        return os.path.join(tempfile.gettempdir(), NOME)


def preparar() -> str:
    """Liga o registro. Devolve o caminho do arquivo."""
    global _pronto
    alvo = caminho()
    if _pronto:
        return alvo

    formato = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S")

    arquivo = RotatingFileHandler(alvo, maxBytes=512 * 1024, backupCount=2,
                                  encoding="utf-8")
    arquivo.setFormatter(formato)

    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(arquivo)

    if sys.stdout is not None and sys.stdout.isatty():
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("  %(message)s"))
        raiz.addHandler(console)

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    _pronto = True
    return alvo


def log(nome: str) -> logging.Logger:
    return logging.getLogger(nome)
