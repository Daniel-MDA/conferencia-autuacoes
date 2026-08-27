"""
Confere se o executável recém-gerado é mesmo o código atual — e se ele abre.

Empacotar "com sucesso" não garante nada: a primeira build deste projeto
terminou sem erro e mesmo assim o `import webview` quebrava, e a aplicação
caía calada para o navegador. Este teste roda o .exe de verdade e verifica:

  1. ele sobe e responde
  2. a versão que ele informa é a de parametros.py
  3. a impressão digital do código empacotado bate com a do disco — é o que
     prova que o Python lá dentro é o atual, e não uma sobra de cache
  4. os arquivos da interface embutidos são idênticos aos do código-fonte

E avisa — sem reprovar — se a janela nativa não abriu. Cair para o navegador
é comportamento previsto (R-02) numa máquina sem o WebView2: é um alerta para
quem gera, não um defeito do pacote.

Chamado pelo gerar_exe.bat. Devolve 0 se estiver tudo certo.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(AQUI, "dist", "ConferenciaAutuacoes.exe")

#: o que o exe serve  ->  o arquivo de origem
ATIVOS = {
    "/estatico/app.js": "autuacao/web/app.js",
    "/estatico/style.css": "autuacao/web/style.css",
    # pela rota estatica, nao por "/": a pagina servida em "/" leva a
    # credencial da sessao injetada e por definicao difere do arquivo
    "/estatico/index.html": "autuacao/web/index.html",
}

VERDE, VERMELHO, AMARELO = "  [ok]   ", "  [FALHA]", "  [aviso]"


def porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def buscar(url: str, segundos: float = 8.0) -> bytes | None:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.read()
        except Exception:                                     # noqa: BLE001
            time.sleep(0.3)
    return None


def digest(texto: str) -> str:
    """Ignora a diferença de fim de linha entre o servido e o do disco."""
    return hashlib.md5(texto.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def impressao_esperada() -> str:
    sys.path.insert(0, AQUI)
    from autuacao import impressao                  # noqa: PLC0415
    return impressao.calcular(AQUI)


def versao_esperada() -> str:
    sys.path.insert(0, AQUI)
    from autuacao import parametros as P            # noqa: PLC0415
    return P.VERSAO


def main() -> int:
    if not os.path.isfile(EXE):
        print(VERMELHO, "dist\\ConferenciaAutuacoes.exe nao existe.")
        return 1

    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    print(f"  Subindo o executavel na porta {porta}...")

    proc = subprocess.Popen([EXE, "--porta", str(porta)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    falhas, avisos = [], []
    try:
        bruto = buscar(base + "/api/inicio", segundos=25)
        if bruto is None:
            print(VERMELHO, "o executavel nao respondeu em 25 s.")
            print("         Veja dist\\ConferenciaAutuacoes.log.")
            return 1
        print(VERDE, "o executavel subiu e respondeu")

        dados = json.loads(bruto.decode("utf-8"))

        esperada = versao_esperada()
        if dados.get("versao") == esperada:
            print(VERDE, f"versao {esperada}, igual a de parametros.py")
        else:
            falhas.append(f"versao empacotada {dados.get('versao')!r} "
                          f"difere de parametros.py ({esperada!r})")

        # a prova de que o Python empacotado e o do disco: comparar os
        # arquivos da interface nao diz nada sobre os modulos .py
        marca = impressao_esperada()
        if dados.get("impressao") == marca:
            print(VERDE, f"impressao do codigo {marca}, igual a do disco")
        else:
            falhas.append(
                "o codigo empacotado nao e o que esta na pasta "
                f"(pacote {dados.get('impressao')!r}, disco {marca!r}) — "
                "gere de novo")

        # o servidor responde ANTES de a janela abrir: main.py sobe o
        # servidor, espera ele atender e SO ENTAO chama a janela. Sem
        # esta espera, a primeira leitura sempre acusaria fallback.
        nativa = dados.get("tem_janela_nativa")
        limite = time.time() + 20
        while not nativa and time.time() < limite:
            time.sleep(1.0)
            outro = buscar(base + "/api/inicio", segundos=3)
            if outro:
                nativa = json.loads(outro.decode("utf-8")).get(
                    "tem_janela_nativa")
        if nativa:
            print(VERDE, "a janela nativa abriu")
        else:
            avisos.append(
                "a janela nativa nao abriu — caiu para o navegador. "
                "Normal em maquina sem o WebView2 Runtime; o motivo "
                "fica em dist\\ConferenciaAutuacoes.log")

        for rota, origem in ATIVOS.items():
            servido = buscar(base + rota, segundos=5)
            caminho = os.path.join(AQUI, origem.replace("/", os.sep))
            if servido is None or not os.path.isfile(caminho):
                falhas.append(f"nao consegui comparar {origem}")
                continue
            disco = io.open(caminho, encoding="utf-8").read()
            if digest(servido.decode("utf-8")) == digest(disco):
                print(VERDE, f"{origem} igual ao codigo-fonte")
            else:
                falhas.append(f"{origem} empacotado difere do codigo-fonte — "
                              f"a build pegou uma versao antiga")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()

    print()
    for a in avisos:
        print(AMARELO, a)
    if falhas:
        for f in falhas:
            print(VERMELHO, f)
        return 1
    print("  O executavel confere com o codigo-fonte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
