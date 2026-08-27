"""
O servidor local que serve a interface e a API.

Fica em 127.0.0.1 numa porta efemera. Nada trafega para fora da maquina: o
unico acesso de rede e a busca das imagens no servidor configurado (RNF-07).

A mesma aplicacao serve os dois modos de exibicao — janela nativa e
navegador (R-02) — porque em ambos a interface e a mesma pagina e as imagens
chegam por <img src="/api/imagem/...">.
"""
from __future__ import annotations

import io
import logging
import os
import socket
import threading

from flask import Flask, Response, jsonify, request, send_file
from werkzeug.utils import secure_filename

from . import guarda
from . import impressao
from . import parametros as P
from . import remessa as remessa_mod
from .dominio import AUTUADO, DESCARTADO
from .relatorio import RelatorioInvalido
from .sessao import SESSAO

#: preenchido pelo janela.py quando ha janela nativa disponivel
ESCOLHER_ARQUIVO = None


def _calar_werkzeug() -> None:
    """
    A aplicacao e local e de um operador so: o aviso de "development server"
    e o log de cada requisicao nao dizem nada ao operador e assustam quem le.
    """
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    try:
        from flask import cli
        cli.show_server_banner = lambda *a, **k: None
    except Exception:                                         # noqa: BLE001
        pass


def criar_app() -> Flask:
    _calar_werkzeug()
    raiz = P.pasta_de_recursos()
    app = Flask(__name__,
                static_folder=os.path.join(raiz, "web"),
                static_url_path="/estatico")
    app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024
    app.json.ensure_ascii = False

    # ───────────────────────────────────────────────────────── pagina
    guarda.instalar(app)

    @app.get("/")
    def pagina():
        caminho = os.path.join(app.static_folder, "index.html")
        with open(caminho, encoding="utf-8") as f:
            html = guarda.injetar_token(f.read())
        return Response(html, mimetype="text/html; charset=utf-8")

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    # ──────────────────────────────────────────────────────── ajudas
    def erro(mensagem: str, codigo: int = 400):
        return jsonify(erro=str(mensagem)), codigo

    def corpo() -> dict:
        return request.get_json(silent=True) or {}

    # ──────────────────────────────────────────────────────── estado
    @app.get("/api/inicio")
    def api_inicio():
        return jsonify({
            "app": P.APP_NOME,
            "versao": P.VERSAO,
            "impressao": impressao.atual(),
            "modulos": [{"chave": k, **v} for k, v in P.MODULOS.items()],
            "motivos": P.MOTIVOS_DESCARTE,
            "motivo_livre": P.MOTIVO_LIVRE,
            "motivo_sem_foto": P.MOTIVO_SEM_FOTO,
            "angulos": P.ANGULOS,
            "min_fotos": P.MIN_FOTOS,
            "max_fotos": P.MAX_FOTOS,
            "fotos_por_pagina": P.FOTOS_POR_PAGINA,
            "rodovia": P.RODOVIA,
            "concessionaria": P.CONCESSIONARIA_RAZAO,
            "declaracao": P.DECLARACAO_RODAPE,
            "campos_laudo": P.CAMPOS_LAUDO,
            "tem_janela_nativa": ESCOLHER_ARQUIVO is not None,
            "estado": SESSAO.estado(),
        })

    @app.get("/api/estado")
    def api_estado():
        return jsonify(SESSAO.estado())

    @app.get("/api/lista")
    def api_lista():
        """Placas, horas e IDs — fixos na sessão, buscados uma vez."""
        return jsonify(SESSAO.lista())

    # ───────────────────────────────────────────────────────── carga
    @app.post("/api/escolher-arquivo")
    def api_escolher():
        """Abre o dialogo nativo do Windows. So existe com janela nativa."""
        if ESCOLHER_ARQUIVO is None:
            return jsonify(disponivel=False)
        caminho = ESCOLHER_ARQUIVO()
        return jsonify(disponivel=True, caminho=caminho or "")

    @app.post("/api/sessao")
    def api_sessao():
        """Abre a sessao. Aceita caminho local ou arquivo enviado."""
        modulo = (request.form.get("modulo")
                  or corpo().get("modulo") or "").strip()
        if modulo not in P.MODULOS:
            return erro("Escolha um dos dois módulos antes de carregar.")

        caminho = (corpo().get("caminho") or request.form.get("caminho") or "").strip()
        enviado = request.files.get("arquivo")

        if enviado and enviado.filename:
            # secure_filename, sempre: o Werkzeug NAO sanitiza `filename`, e
            # um nome como ..\..\XLSTART\x.xlsx escreveria fora da pasta
            # temporaria — inclusive numa pasta que o Excel abre sozinho.
            nome = secure_filename(enviado.filename) or "planilha.xlsx"
            if not nome.lower().endswith((".xlsx", ".xlsm")):
                return erro("Envie o .xlsx exportado do Backoffice.")
            import tempfile
            caminho = os.path.join(tempfile.gettempdir(), nome)
            enviado.save(caminho)
        elif not caminho:
            return erro("Nenhum arquivo recebido.")
        elif not os.path.isfile(caminho):
            return erro(f"Arquivo não encontrado: {caminho}")

        try:
            resumo = SESSAO.iniciar(modulo, caminho)
        except RelatorioInvalido as e:
            return erro(str(e))
        except Exception as e:                                # noqa: BLE001
            return erro(f"Não consegui ler a planilha: {e}")

        return jsonify(ok=True, resumo=resumo, estado=SESSAO.estado())

    @app.post("/api/encerrar-sessao")
    def api_encerrar_sessao():
        SESSAO.fechar()
        return jsonify(ok=True, estado=SESSAO.estado())

    @app.post("/api/descartar-rascunho")
    def api_descartar_rascunho():
        SESSAO.descartar_rascunho()
        return jsonify(ok=True, estado=SESSAO.estado())

    # ─────────────────────────────────────────────────────── transito
    @app.get("/api/transito/<int:indice>")
    def api_transito(indice: int):
        try:
            return jsonify(SESSAO.transito(indice))
        except ValueError as e:
            return erro(str(e), 404)

    @app.post("/api/decisao")
    def api_decisao():
        d = corpo()
        indice = d.get("indice")
        desfecho = d.get("decisao")
        if not isinstance(indice, int):
            return erro("Índice inválido.")
        if desfecho not in (AUTUADO, DESCARTADO, None):
            return erro("Decisão inválida.")
        try:
            estado = SESSAO.decidir(indice, desfecho,
                                    str(d.get("motivo") or ""),
                                    str(d.get("descricao") or ""))
        except (ValueError, IndexError) as e:
            return erro(str(e))
        return jsonify(ok=True, estado=estado)

    @app.post("/api/rebuscar")
    def api_rebuscar():
        indice = corpo().get("indice")
        if not isinstance(indice, int):
            return erro("Índice inválido.")
        SESSAO.rebuscar(indice)
        return jsonify(ok=True)

    # ───────────────────────────────────────────────────────── fotos
    @app.post("/api/foto")
    def api_foto():
        d = corpo()
        indice = d.get("indice")
        acao = d.get("acao")
        if not isinstance(indice, int):
            return erro("Índice inválido.")
        try:
            if acao == "alternar":
                return jsonify(SESSAO.alternar_foto(indice, str(d.get("codigo"))))
            if acao == "sugerida":
                return jsonify(SESSAO.selecao_sugerida(indice))
            if acao == "limpar":
                return jsonify(SESSAO.definir_selecao(indice, []))
            if acao == "definir":
                return jsonify(SESSAO.definir_selecao(
                    indice, list(d.get("codigos") or [])))
        except (ValueError, IndexError) as e:
            return erro(str(e))
        return erro("Ação desconhecida.")

    @app.get("/api/imagem/<int:indice>/<codigo>")
    def api_imagem(indice: int, codigo: str):
        rel = SESSAO.relatorio
        if rel is None or not 0 <= indice < len(rel.transitos):
            return "", 404
        img = rel.transitos[indice].imagem(codigo)
        if img is None or not img.caminho_local:
            return "", 404

        largura = request.args.get("w", type=int)
        if largura and largura > 0:
            dados = _miniatura(img.caminho_local, largura)
            if dados:
                return _com_cache(send_file(io.BytesIO(dados),
                                            mimetype="image/jpeg"))
        try:
            return _com_cache(send_file(img.caminho_local,
                                        mimetype="image/jpeg"))
        except OSError:
            return "", 404

    # ─────────────────────────────────────────────────────── remessa
    @app.get("/api/resumo")
    def api_resumo():
        return jsonify(SESSAO.resumo_final())

    @app.post("/api/remessa")
    def api_remessa():
        rel = SESSAO.relatorio
        if rel is None or not SESSAO.modulo:
            return erro("Nenhuma sessão aberta.")
        pasta = (corpo().get("pasta") or "").strip() or None
        try:
            resultado = remessa_mod.gerar(rel, SESSAO.modulo, pasta)
        except ValueError as e:
            return erro(str(e))
        except Exception as e:                                # noqa: BLE001
            return erro(f"Falha ao gerar a remessa: {e}")

        SESSAO.pasta_remessa = resultado["pasta"]
        SESSAO.versao_remessa += 1
        SESSAO.salvar_rascunho()      # marca a sessao como concluida
        try:
            remessa_mod.abrir_no_explorador(resultado["pasta"])
        except Exception:                                     # noqa: BLE001
            pass
        return jsonify(ok=True, **resultado)

    @app.post("/api/abrir-pasta")
    def api_abrir_pasta():
        pasta = (corpo().get("pasta") or SESSAO.pasta_remessa or "").strip()
        try:
            remessa_mod.abrir_no_explorador(pasta)
        except Exception as e:                                # noqa: BLE001
            return erro(str(e))
        return jsonify(ok=True)

    return app


# ──────────────────────────────────────────────────────────── auxiliares
def _com_cache(resposta):
    """
    Dentro de uma sessao a imagem de um transito nunca muda: o cache local
    e imutavel ate o programa fechar. Sem estes cabecalhos o WebView
    rebuscava toda miniatura a cada redesenho da tira — e cada rebusca
    reencodava a imagem no servidor.
    """
    resposta.headers["Cache-Control"] = "private, max-age=86400, immutable"
    return resposta


#: memoria das miniaturas ja geradas: caminho+largura -> bytes
_MINIATURAS: dict[tuple, bytes] = {}
_LIMITE_MINIATURAS = 400


def _miniatura(caminho: str, largura: int) -> bytes | None:
    """Miniatura, para a tira nao carregar as imagens em tamanho cheio."""
    try:
        marca = (caminho, largura, os.path.getmtime(caminho))
    except OSError:
        return None
    pronta = _MINIATURAS.get(marca)
    if pronta is not None:
        return pronta

    try:
        from PIL import Image
        # teto de pixels: a imagem vem de fora e uma "bomba de descompressao"
        # travaria o processo inteiro na hora de decodificar
        Image.MAX_IMAGE_PIXELS = 80_000_000
        with Image.open(caminho) as im:
            if im.width <= largura:
                return None
            altura = max(1, round(im.height * largura / im.width))
            im = im.convert("RGB").resize((largura, altura), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
            dados = buf.getvalue()
    except Exception:                                         # noqa: BLE001
        return None

    if len(_MINIATURAS) > _LIMITE_MINIATURAS:
        _MINIATURAS.clear()
    _MINIATURAS[marca] = dados
    return dados


def porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def subir_em_thread(app: Flask, porta: int) -> threading.Thread:
    def rodar():
        app.run(host="127.0.0.1", port=porta, debug=False,
                threaded=True, use_reloader=False)

    t = threading.Thread(target=rodar, name="servidor", daemon=True)
    t.start()
    return t
