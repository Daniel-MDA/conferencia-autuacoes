"""
A janela nativa — e o plano B quando ela nao existe.

RNF-02 pede uma janela de verdade, sem barra de endereco. Quem desenha essa
janela e o pywebview, apoiado no WebView2 do proprio Windows.

R-02: o WebView2 vem por padrao no Windows 11 e na maioria dos Windows 10
atualizados, mas nao em todos. Quando ele falta, a aplicacao NAO pode
simplesmente nao abrir: ela cai para o navegador padrao e avisa o operador,
que e exatamente como a versao 1.0 funcionava.
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
import webbrowser

from . import parametros as P
from . import servidor as servidor_mod
from .registro import log
from .sessao import SESSAO

_log = log("janela")


def _esperar_servidor(url: str, segundos: float = 12.0) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except urllib.error.HTTPError:
            return True          # respondeu, mesmo que com erro: esta de pe
        except Exception:                                     # noqa: BLE001
            time.sleep(0.15)
    return False


def _dialogo_pywebview(webview, janela):
    """Devolve uma funcao que abre o seletor de arquivos do Windows."""
    def escolher() -> str | None:
        try:
            tipos = ("Relatório do Backoffice (*.xlsx;*.xlsm)",)
            r = janela.create_file_dialog(webview.OPEN_DIALOG,
                                          allow_multiple=False,
                                          file_types=tipos)
            if not r:
                return None
            return r[0] if isinstance(r, (list, tuple)) else str(r)
        except Exception:                                     # noqa: BLE001
            return None
    return escolher


def abrir(url: str, forcar_navegador: bool = False) -> str:
    """
    Abre a interface. Devolve "nativa" ou "navegador", conforme o que deu.

    No modo nativo bloqueia ate a janela ser fechada; no modo navegador
    quem segura a aplicacao de pe e o chamador, por `esperar()`.
    """
    if forcar_navegador:
        webbrowser.open(url)
        return "navegador"

    try:
        import webview                                       # type: ignore
    except Exception:                                         # noqa: BLE001
        _log.exception("não consegui importar o pywebview")
        _log.warning("abrindo no navegador padrão")
        webbrowser.open(url)
        return "navegador"

    try:
        janela = webview.create_window(
            f"{P.APP_NOME} {P.VERSAO}",
            url,
            width=P.LARGURA_JANELA,
            height=P.ALTURA_JANELA,
            min_size=(P.LARGURA_MINIMA, P.ALTURA_MINIMA),
            confirm_close=False,
        )
        servidor_mod.ESCOLHER_ARQUIVO = _dialogo_pywebview(webview, janela)

        def ao_fechar():
            SESSAO.encerrar()                                 # RN-16

        try:
            janela.events.closed += ao_fechar
        except Exception:                                     # noqa: BLE001
            pass

        # getattr, nao acesso direto: um diagnostico nunca pode derrubar o
        # que ele observa. A versao 6 do pywebview nao expoe __version__, e o
        # acesso direto caia no except abaixo, mandando a aplicacao para o
        # modo de reserva por causa da propria linha de log.
        _log.info("abrindo a janela nativa (pywebview %s)",
                  getattr(webview, "__version__", "versão desconhecida"))
        webview.start()
        _log.info("janela nativa fechada")
        return "nativa"

    except Exception as e:                                    # noqa: BLE001
        servidor_mod.ESCOLHER_ARQUIVO = None
        _log.exception("a janela nativa não abriu (%s)", e)
        _log.warning("costuma ser a falta do WebView2 Runtime — "
                     "abrindo no navegador padrão")
        webbrowser.open(url)
        return "navegador"


# ══════════════════════════════════════════════════ modo de reserva
def _tem_console() -> bool:
    """Empacotado com console=False não há janela preta para fechar."""
    try:
        return sys.stdout is not None and sys.stdout.isatty()
    except Exception:                                         # noqa: BLE001
        return False


def _janelinha_de_espera(url: str) -> bool:
    """
    Uma janela mínima, só para o operador ter o que fechar.

    Sem ela, o executável empacotado sem console ficaria rodando invisível e
    só morreria pelo Gerenciador de Tarefas.
    """
    try:
        import tkinter as tk
    except ImportError:
        return False

    aviso = ("A aplicação está aberta no seu navegador."
             "\n\n"
             "Esta janela não faz parte do programa: ela existe só para "
             "manter o servidor local de pé."
             "\n"
             "Feche-a para encerrar.")

    try:
        raiz = tk.Tk()
        raiz.title(f"{P.APP_NOME} {P.VERSAO}")
        raiz.geometry("470x215")
        raiz.resizable(False, False)

        tk.Label(raiz, text=P.APP_NOME,
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 4))
        tk.Label(raiz, text=aviso, justify="center", wraplength=420,
                 font=("Segoe UI", 9)).pack(padx=20)
        tk.Label(raiz, text=url, font=("Consolas", 8),
                 fg="#666666").pack(pady=(10, 0))
        tk.Button(raiz, text="Abrir de novo no navegador",
                  command=lambda: webbrowser.open(url)).pack(pady=12)

        raiz.mainloop()
        return True
    except Exception:                                         # noqa: BLE001
        return False


def esperar(url: str) -> None:
    """No modo navegador, alguma coisa precisa segurar a aplicação de pé."""
    if not _tem_console() and _janelinha_de_espera(url):
        return

    if _tem_console():
        print("\n  Feche esta janela para encerrar a aplicação.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


__all__ = ["abrir", "esperar", "_esperar_servidor"]
