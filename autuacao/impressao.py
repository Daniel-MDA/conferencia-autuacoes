"""
Impressão digital do código-fonte.

Serve para responder, com prova, a uma pergunta que aparece sempre:
*este executável é o código que está na minha pasta agora?*

O empacotador reaproveita cache, o `.exe` fica com data de hoje mesmo quando
o conteúdo é de ontem, e comparar datas não decide nada. Então o valor é
calculado sobre o conteúdo dos arquivos:

  * na geração, o `.spec` chama `calcular()` e grava o resultado dentro do
    pacote;
  * ao rodar, a aplicação devolve esse valor em `/api/inicio`;
  * o `verificar_build.py` recalcula a partir do disco e compara.

Diferiu, o pacote é velho — não importa o que a data diga.
"""
from __future__ import annotations

import hashlib
import os
import sys

#: o que entra na conta: o código e a interface, nada de artefato
ALVOS = (
    ("", ("main.py",)),
    ("autuacao", (".py",)),
    ("autuacao/web", (".html", ".css", ".js")),
)

NOME_EMBUTIDO = "impressao.txt"


def arquivos(raiz: str) -> list[str]:
    achados: list[str] = []
    for pasta, filtros in ALVOS:
        alvo = os.path.join(raiz, pasta.replace("/", os.sep)) if pasta else raiz
        if not os.path.isdir(alvo):
            continue
        for nome in sorted(os.listdir(alvo)):
            caminho = os.path.join(alvo, nome)
            if not os.path.isfile(caminho):
                continue
            if filtros[0].startswith("."):
                if os.path.splitext(nome)[1].lower() in filtros:
                    achados.append(caminho)
            elif nome in filtros:
                achados.append(caminho)
    return achados


def calcular(raiz: str) -> str:
    """
    Resumo do conteúdo de todos os fontes.

    O fim de linha é normalizado antes de entrar na conta: um arquivo salvo
    com CRLF e outro com LF são o mesmo código, e sem isso a comparação
    acusaria diferença onde não há.
    """
    h = hashlib.sha256()
    for caminho in arquivos(raiz):
        rel = os.path.relpath(caminho, raiz).replace(os.sep, "/")
        h.update(rel.encode("utf-8") + b"\0")
        with open(caminho, "rb") as f:
            h.update(f.read().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()[:16]


def raiz_do_projeto() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def atual() -> str:
    """Empacotado, lê o valor gravado na geração; do fonte, calcula na hora."""
    if getattr(sys, "frozen", False):
        alvo = os.path.join(sys._MEIPASS, NOME_EMBUTIDO)   # type: ignore
        try:
            with open(alvo, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return "(não gravada)"
    return calcular(raiz_do_projeto())
