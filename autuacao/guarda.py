"""
Proteção do servidor local.

A aplicação escuta em 127.0.0.1, o que costuma passar por "seguro" e não é:
qualquer página aberta no navegador do operador consegue disparar um POST
para 127.0.0.1 sem precisar de CORS — o navegador bloqueia a *leitura* da
resposta, mas a requisição chega e é executada. Sem defesa, um site
qualquer poderia encerrar a sessão do operador, apagar o rascunho ou
mandar gerar uma remessa.

Duas barreiras, ambas baratas:

  * ORIGEM — toda requisição que muda estado precisa vir da própria página.
    Navegadores mandam o cabeçalho `Origin` em POST, inclusive nos
    formulários HTML, e não deixam a página forjá-lo.

  * CREDENCIAL — um segredo sorteado a cada execução, injetado na página e
    devolvido em todo POST. Fecha o caso de quem chega sem `Origin`
    (curl, script local) e o de uma porta fixa e previsível.

GET fica de fora de propósito: `<img src="/api/imagem/...">` não manda
cabeçalho nenhum, e ler imagem não muda nada.
"""
from __future__ import annotations

import secrets

from flask import jsonify, request

CABECALHO = "X-Autuacao-Token"
_MARCADOR = "__TOKEN_DA_SESSAO__"

#: sorteado uma vez por execução do programa
TOKEN = secrets.token_urlsafe(24)

SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})


def injetar_token(html: str) -> str:
    """Troca o marcador da página pelo segredo desta execução."""
    return html.replace(_MARCADOR, TOKEN)


def instalar(app) -> None:
    @app.before_request
    def _conferir():                                          # noqa: ANN202
        if request.method in SEGUROS:
            return None

        origem = request.headers.get("Origin")
        if origem and origem.rstrip("/") != request.host_url.rstrip("/"):
            return jsonify(erro="Requisição recusada: origem externa."), 403

        if not secrets.compare_digest(
                request.headers.get(CABECALHO, ""), TOKEN):
            return jsonify(
                erro="Requisição recusada: credencial da sessão ausente ou "
                     "inválida. Recarregue a página."), 403
        return None
