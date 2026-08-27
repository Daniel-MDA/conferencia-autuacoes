"""
Descoberta e download das imagens de cada transito.

Caminho no servidor:
    {protocolo}://{servidor}/{raiz}{AAAAMMDD}/{pasta}/{ID}-{angulo}{nn}.jpg

A pasta sao os 9 primeiros caracteres do ID (RN-17 / RF-11). A regra foi
medida sobre 3.419 transitos de 5 pracas: a coluna Pista do relatorio
discorda do ID em 34% das linhas, e quem manda e o ID. Nao ha tentativa
dupla como na versao 1.0.

A busca e SOB DEMANDA (RF-13): o transito que esta na tela e os vizinhos
imediatos entram na fila primeiro. O operador comeca a conferir antes de o
relatorio inteiro ter sido baixado.

O cache vive na pasta temporaria e e apagado ao encerrar (RN-16 / RF-54).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3

from . import parametros as P
from .dominio import Imagem, Transito

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#: assinaturas de arquivo aceitas — o servidor as vezes devolve HTML com 200
ASSINATURAS = (b"\xff\xd8", b"\x89P", b"BM", b"GI")


def _pre_selecionar(t: Transito) -> None:
    """
    RN-05 — marca a foto da placa e a panoramica assim que elas chegam.

    Tem de acontecer ANTES de `imagens_buscadas` virar True: a interface para
    de consultar quando ve essa marca, e se a selecao entrasse depois, um
    pedido que caisse na janela entre as duas coisas deixaria o operador
    olhando "0 de 8" numa foto que ja estava na tela.
    """
    if t.decisao is None and not t.selecionadas:
        t.selecionadas = t.selecao_sugerida()


class Buscador:
    def __init__(self, simulado: bool = False):
        self.simulado = simulado or P.MODO_DEMONSTRACAO

        marca = hashlib.md5(
            f"{P.PROTOCOLO}|{P.SERVIDOR}|{P.RAIZ_FOTOS}|{self.simulado}"
            .encode("utf-8")).hexdigest()[:10]
        self.cache = os.path.join(tempfile.gettempdir(), f"autuacao_img_{marca}")
        os.makedirs(self.cache, exist_ok=True)

        self._local = threading.local()
        self._lock = threading.Lock()
        self._na_fila: set[str] = set()
        self._piscina = ThreadPoolExecutor(
            max_workers=P.DOWNLOADS_PARALELOS,
            thread_name_prefix="imagens")
        self._encerrando = False
        self.aviso: str | None = None      # ultima falha de rede, para a tela

    # ─────────────────────────────────────────────────────────── url
    @staticmethod
    def url(transito: Transito, angulo: str, tomada: int) -> str:
        return (f"{P.PROTOCOLO}://{P.SERVIDOR}/{P.RAIZ_FOTOS}"
                f"{transito.data_pasta}/{transito.pasta_servidor}/"
                f"{transito.id}-{angulo}{tomada:02d}.jpg")

    def _sessao(self) -> requests.Session:
        s = getattr(self._local, "sessao", None)
        if s is None:
            s = requests.Session()
            s.headers["User-Agent"] = f"ConferenciaAutuacoes/{P.VERSAO}"
            self._local.sessao = s
        return s

    # ───────────────────────────────────────────────────────── baixar
    def _baixar(self, url: str, destino: str) -> tuple[bool, str]:
        """Devolve (ok, erro). Grava em destino quando ok."""
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            return True, ""
        try:
            r = self._sessao().get(url, timeout=P.TIMEOUT_SEGUNDOS,
                                   verify=P.VERIFICAR_CERTIFICADO)
        except requests.exceptions.ConnectTimeout:
            return False, "servidor não respondeu (timeout)"
        except requests.exceptions.ConnectionError:
            return False, "sem conexão com o servidor — a VPN está ligada?"
        except Exception as e:                                # noqa: BLE001
            return False, type(e).__name__

        if r.status_code == 404:
            return False, "HTTP 404"
        if r.status_code in (401, 403):
            return False, f"HTTP {r.status_code} — o servidor exige autenticação"
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        if len(r.content) < 8 or not r.content.startswith(ASSINATURAS):
            return False, "a resposta não é uma imagem"

        parcial = destino + ".parcial"
        try:
            with open(parcial, "wb") as f:
                f.write(r.content)
            os.replace(parcial, destino)
        except OSError as e:
            return False, f"não consegui gravar no cache: {e}"
        return True, ""

    # ──────────────────────────────────────────────────────── buscar
    def buscar(self, t: Transito) -> Transito:
        """Preenche t.imagens. Nunca levanta excecao."""
        if t.imagens_buscadas:
            return t
        if self.simulado:
            _simular(t, self.cache)
            _pre_selecionar(t)
            t.imagens_buscadas = True
            return t

        achadas: list[Imagem] = []
        ultimo_erro = ""

        for angulo in t.ordem_angulos:
            for tomada in range(1, P.MAX_TOMADAS + 1):
                url = self.url(t, angulo, tomada)
                destino = os.path.join(
                    self.cache, f"{t.id}-{angulo}{tomada:02d}.jpg")
                ok, erro = self._baixar(url, destino)
                if ok:
                    achadas.append(Imagem(angulo=angulo, tomada=tomada,
                                          url=url, caminho_local=destino))
                else:
                    ultimo_erro = erro
                    # sem a tomada N nao existe a N+1 (RF-12)
                    if tomada == 1:
                        achadas.append(Imagem(angulo=angulo, tomada=1,
                                              url=url, erro=erro))
                    break

        t.imagens = [i for i in achadas if i.ok]
        if not t.imagens:
            # guarda uma entrada com erro por angulo, para o diagnostico (RF-15)
            t.imagens = []
            t.erro_busca = ultimo_erro or "nenhuma imagem encontrada"
            t.url_tentada = self.url(t, t.ordem_angulos[0], 1)   # type: ignore
        t.ordenar_imagens()
        _pre_selecionar(t)
        t.imagens_buscadas = True
        return t

    # ────────────────────────────────────────────── busca sob demanda
    def agendar(self, transitos: list[Transito], indice: int) -> None:
        """
        Poe na fila o transito visivel e a janela de vizinhos (RF-13).
        Retorna na hora; quem quiser saber se chegou consulta o estado.
        """
        if self._encerrando:
            return
        janela = P.JANELA_ANTECIPACAO
        ordem = [indice]
        for d in range(1, janela + 1):
            ordem.extend([indice + d, indice - d])

        for i in ordem:
            if not 0 <= i < len(transitos):
                continue
            t = transitos[i]
            if t.imagens_buscadas:
                continue
            with self._lock:
                if t.id in self._na_fila:
                    continue
                self._na_fila.add(t.id)
            self._piscina.submit(self._tarefa, t)

    def _tarefa(self, t: Transito) -> None:
        try:
            self.buscar(t)
            if t.erro_busca:
                self.aviso = t.erro_busca
        except Exception as e:                                # noqa: BLE001
            t.imagens = []
            t.erro_busca = str(e)
            t.imagens_buscadas = True
        finally:
            with self._lock:
                self._na_fila.discard(t.id)

    # ───────────────────────────────────────────────────────── cache
    def encerrar(self, limpar: bool = True) -> None:
        """RN-16 — o cache nao sobrevive ao fechamento da aplicacao."""
        self._encerrando = True
        self._piscina.shutdown(wait=False, cancel_futures=True)
        if limpar:
            self.limpar_cache()

    def limpar_cache(self) -> None:
        try:
            shutil.rmtree(self.cache, ignore_errors=True)
        except Exception:                                     # noqa: BLE001
            pass

    def tamanho_cache(self) -> int:
        total = 0
        for raiz, _, arquivos in os.walk(self.cache):
            for a in arquivos:
                try:
                    total += os.path.getsize(os.path.join(raiz, a))
                except OSError:
                    pass
        return total


# ──────────────────────────────────────────────── modo demonstracao
def _simular(t: Transito, cache: str) -> None:
    """
    RF-55 — imagens sinteticas em 4:3, para treinar e apresentar sem VPN.
    Ligado so por --demo na linha de comando.
    """
    from PIL import Image as PILImage, ImageDraw

    largura, altura = 1024, 768
    quantas = {"F": 2, "P": 1, "L": 1, "T": 1}

    imagens: list[Imagem] = []
    for angulo in t.ordem_angulos:
        for tomada in range(1, quantas.get(angulo, 1) + 1):
            codigo = f"{angulo}{tomada:02d}"
            destino = os.path.join(cache, f"SIM-{t.id}-{codigo}.jpg")
            if not os.path.exists(destino):
                img = PILImage.new("RGB", (largura, altura), (26, 32, 38))
                d = ImageDraw.Draw(img)
                for y in range(0, altura, 48):
                    d.line([(0, y), (largura, y)], fill=(33, 40, 47))
                d.rectangle([30, 30, largura - 30, altura - 30],
                            outline=(90, 102, 114), width=2)
                linhas = [
                    "MODO DEMONSTRACAO",
                    "",
                    f"Camera    {codigo}  ({P.ANGULOS.get(angulo, angulo)})",
                    f"Transito  {t.id}",
                    f"Data/hora {t.data} {t.hora}",
                    f"Placa     {t.placa or '-'}",
                    f"Pasta     {t.pasta_servidor}",
                ]
                y = 90
                for i, linha in enumerate(linhas):
                    d.text((70, y), linha,
                           fill=(242, 177, 52) if i == 0 else (226, 232, 238))
                    y += 34
                d.text((70, altura - 70),
                       "Imagem gerada localmente — nao veio do servidor",
                       fill=(130, 142, 154))
                img.save(destino, "JPEG", quality=85)
            imagens.append(Imagem(angulo=angulo, tomada=tomada,
                                  url=f"simulado://{t.id}-{codigo}.jpg",
                                  caminho_local=destino))

    t.imagens = imagens
    t.ordenar_imagens()
