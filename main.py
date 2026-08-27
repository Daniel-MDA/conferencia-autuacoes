"""
Conferência de Autuações — ponto de entrada.

    python main.py               abre na janela nativa
    python main.py --demo        imagens sintéticas, sem acessar o servidor
    python main.py --navegador   força o modo navegador
    python main.py --porta 9000  fixa a porta (padrão: uma porta livre)

Nada trafega para fora da máquina: o único acesso de rede é a busca das
imagens no servidor configurado em autuacao/parametros.py.
"""
from __future__ import annotations

import argparse
import sys

from autuacao import janela as janela_mod
from autuacao import parametros as P
from autuacao import registro
from autuacao import servidor as servidor_mod
from autuacao.sessao import SESSAO


def main() -> int:
    ap = argparse.ArgumentParser(description=P.APP_NOME, add_help=True)
    ap.add_argument("--demo", action="store_true",
                    help="usa imagens sintéticas, sem acessar o servidor")
    ap.add_argument("--navegador", action="store_true",
                    help="abre no navegador padrão em vez da janela nativa")
    ap.add_argument("--porta", type=int, default=0,
                    help="porta do servidor local (padrão: uma porta livre)")
    args = ap.parse_args()

    arquivo_log = registro.preparar()
    _log = registro.log("main")
    _log.info("%s %s — iniciando (congelado=%s)", P.APP_NOME, P.VERSAO,
              getattr(sys, "frozen", False))

    SESSAO.simulado = bool(args.demo)

    porta = args.porta or servidor_mod.porta_livre()
    url = f"http://127.0.0.1:{porta}/"

    print(f"\n  {P.APP_NOME} {P.VERSAO}")
    if args.demo:
        print("  MODO DEMONSTRAÇÃO — imagens sintéticas, sem acessar o servidor")
    else:
        print(f"  Servidor de imagens: {P.PROTOCOLO}://{P.SERVIDOR}")
    print(f"  Interface em: {url}")
    print(f"  Registro em:  {arquivo_log}")

    app = servidor_mod.criar_app()
    servidor_mod.subir_em_thread(app, porta)

    if not janela_mod._esperar_servidor(url):
        print("\n  O servidor local não subiu. Verifique se a porta está livre.")
        return 1

    try:
        modo = janela_mod.abrir(url, forcar_navegador=args.navegador)
        if modo == "navegador":
            janela_mod.esperar(url)
    finally:
        SESSAO.encerrar()          # RN-16 — o cache de imagens vai junto
        print("  Cache de imagens apagado. Até logo.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
