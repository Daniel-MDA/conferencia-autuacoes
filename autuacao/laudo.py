"""
Geracao do laudo — um PDF por transito autuado.

    +--------------------------------------------------------+
    |  [logo]      COMPROVACAO DE TRANSITO - CONTRAMAO        |
    +--------------------------------------------------------+
    Analisado por usuario 00598 em 25/08/2026 12:00:02

    DADOS
    Data      Hora            ID
    Rodovia   Praca (cidade,  Faixa - Sentido - Direcao
              KM)             (em contramao, o sentido sai invertido)
    Placa     Categoria       Velocidade

    EVIDENCIA FOTOGRAFICA
    +------------------+  +------------------+
    |     foto 4:3     |  |     foto 4:3     |
    +------------------+  +------------------+
    Frontal - ...-F01.jpg  Panoramica - ...-P01.jpg
    +------------------+  +------------------+
    |     foto 4:3     |  |     foto 4:3     |
    +------------------+  +------------------+

    Emitido por Concessionaria Rodovia Exemplo S.A.
    Este documento e apenas uma evidencia fotografica ...
                                            Pagina 1 de 2

A4 retrato sempre. Ate 4 fotos por pagina, ate 2 paginas (RN-04). O
cabecalho e o rodape se repetem em toda pagina: cada uma e um documento
completo por si.

Todo o desenho do documento esta neste arquivo — nenhuma outra parte da
aplicacao sabe como o laudo e montado (RNF-15).
"""
from __future__ import annotations

import os

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from . import parametros as P
from .dominio import Relatorio, Transito
from .relatorio import linha_analise

# Teto de pixels ao decodificar: as fotos vem de um servidor externo e uma
# imagem forjada com dimensoes absurdas travaria o processo na decodificacao.
PILImage.MAX_IMAGE_PIXELS = 80_000_000

# ─────────────────────────────────────────────────────────────── medidas
LARGURA, ALTURA = A4                     # 210 x 297 mm
MARGEM = 12 * mm
LARGURA_UTIL = LARGURA - 2 * MARGEM      # 186 mm

CAIXA_TOPO_H = 20.5 * mm
#: espaco maximo da logo. A marca de referencia e quase quadrada (1,21:1), nao
#: uma faixa: com a altura antiga de 13 mm ela saia com 15,7 mm de largura,
#: pequena demais para ler o nome.
LOGO_MAX = (40 * mm, 15.5 * mm)

CALHA = 6 * mm
COLUNAS_FOTO = 2
LARGURA_FOTO = (LARGURA_UTIL - CALHA * (COLUNAS_FOTO - 1)) / COLUNAS_FOTO
ALTURA_FOTO = LARGURA_FOTO * P.PROPORCAO_FOTO[1] / P.PROPORCAO_FOTO[0]
ALTURA_LEGENDA = 4 * mm
ESPACO_LINHA = 5 * mm
#: onde comeca o rodape — a grade de fotos nao passa daqui
TOPO_RODAPE = MARGEM + 20.5 * mm

# ─────────────────────────────────────────────────────────────── cores
TINTA = colors.HexColor("#101418")
ROTULO = colors.HexColor("#6a747d")
LINHA = colors.HexColor("#101418")
MOLDURA_FOTO = colors.HexColor("#8f9aa3")
FUNDO_FOTO = colors.HexColor("#11161a")
FINA = colors.HexColor("#c9d0d6")


# ═════════════════════════════════════════════════════════════ auxiliares
def _txt(v) -> str:
    s = "" if v is None else str(v).strip()
    return s if s else "-"


def _valor(chave: str, t: Transito) -> str:
    if chave == "data":
        return _txt(t.data)
    if chave == "hora":
        return _txt(t.hora)
    if chave == "id":
        return t.id
    if chave == "rodovia":
        return _txt(P.RODOVIA)
    if chave == "praca":
        return _txt(t.praca)
    if chave == "pista":
        return _txt(t.pista)
    if chave == "faixa_sentido":
        return _txt(t.faixa_sentido)
    if chave == "placa":
        return _txt(t.placa)
    if chave == "categoria":
        return _txt(t.categoria)
    if chave == "velocidade":
        v = t.velocidade
        return f"{v} km/h" if v else "-"
    return "-"


def _complemento(chave: str, t: Transito) -> str:
    """
    Texto secundario, em cinza, na mesma linha do valor.

    A praca sai como "01 - Cidade Exemplo - KM 000,000": o numero em destaque,
    e por ele que a PRF localiza o ponto, e a cidade e o quilometro logo
    depois, para quem nao decora numero de praca.
    """
    if chave == "praca":
        return t.praca_local
    return ""


def nome_arquivo(t: Transito, modulo: str) -> str:
    return t.nome_laudo(modulo)


def _encolher(c, texto: str, fonte: str, tamanho: float, largura: float) -> float:
    """Devolve o maior corpo <= tamanho que faz o texto caber na largura."""
    while tamanho > 4.5 and c.stringWidth(texto, fonte, tamanho) > largura:
        tamanho -= 0.25
    return tamanho


# ═══════════════════════════════════════════════════════════ cabecalho
def _cabecalho(c, modulo: str, rel: Relatorio) -> float:
    """Desenha a caixa do topo. Devolve o Y da base dela."""
    base = ALTURA - MARGEM - CAIXA_TOPO_H
    c.setStrokeColor(LINHA)
    c.setLineWidth(0.8)
    c.rect(MARGEM, base, LARGURA_UTIL, CAIXA_TOPO_H, stroke=1, fill=0)

    x_logo = MARGEM + 6 * mm
    fim_logo = x_logo
    caminho = P.caminho_logo()
    desenhou = False
    if caminho:
        try:
            with PILImage.open(caminho) as im:
                lo, al = im.size
            esc = min(LOGO_MAX[0] / lo, LOGO_MAX[1] / al)
            w, h = lo * esc, al * esc
            c.drawImage(caminho, x_logo, base + (CAIXA_TOPO_H - h) / 2,
                        width=w, height=h, mask="auto",
                        preserveAspectRatio=True)
            fim_logo = x_logo + w
            desenhou = True
        except Exception:                                     # noqa: BLE001
            desenhou = False

    if not desenhou:
        nome = rel.concessionaria.strip() or "Concessionária"
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(TINTA)
        c.drawString(x_logo, base + CAIXA_TOPO_H / 2 - 4, nome)
        fim_logo = x_logo + c.stringWidth(nome, "Helvetica-Bold", 12)

    titulo = P.MODULOS[modulo]["titulo_laudo"].upper()
    esquerda = fim_logo + 5 * mm
    direita = LARGURA - MARGEM - 5 * mm
    corpo = _encolher(c, titulo, "Helvetica-Bold", 12, direita - esquerda)
    c.setFont("Helvetica-Bold", corpo)
    c.setFillColor(TINTA)
    c.drawCentredString((esquerda + direita) / 2,
                        base + CAIXA_TOPO_H / 2 - corpo * 0.36, titulo)
    return base


# ═════════════════════════════════════════════════════════════ dados
def _rotulo_secao(c, y: float, texto: str) -> float:
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(TINTA)
    c.drawString(MARGEM, y, texto.upper())
    c.setStrokeColor(FINA)
    c.setLineWidth(0.4)
    c.line(MARGEM, y - 1.6 * mm, LARGURA - MARGEM, y - 1.6 * mm)
    return y - 1.6 * mm


def _ajustar(c, texto: str, fonte: str, largura: float,
             corpo_max: float = 9, minimo: float = 6.0,
             max_linhas: int = 2) -> tuple[float, list[str]]:
    """
    O maior corpo que faz o texto caber em ate max_linhas linhas.

    Um campo so precisa das duas: faixa/sentido junta quatro informacoes
    ("01 - Acostamento - Norte - Decrescente - Exemplo B"). Encolher ate
    caber numa linha o deixaria ilegivel; quebrar preserva o corpo dos
    outros oito campos, que continuam numa linha cada.
    """
    corpo = corpo_max
    while corpo > minimo:
        linhas = _quebrar(c, texto, fonte, corpo, largura, max_linhas)
        if all(c.stringWidth(l, fonte, corpo) <= largura for l in linhas):
            return corpo, linhas
        corpo -= 0.25
    return corpo, _quebrar(c, texto, fonte, corpo, largura, max_linhas)


def _bloco_dados(c, t: Transito, y: float) -> float:
    """Nove campos em tres linhas de tres (RF-41). Devolve o Y final."""
    largura_col = LARGURA_UTIL / 3
    util = largura_col - 4 * mm
    altura_linha = 7.6 * mm
    entrelinha = 3.2 * mm
    y -= 4.4 * mm

    for i in range(0, len(P.CAMPOS_LAUDO), 3):
        celulas = []
        for rotulo, chave in P.CAMPOS_LAUDO[i:i + 3]:
            corpo, linhas = _ajustar(c, _valor(chave, t), "Helvetica-Bold", util)
            celulas.append((rotulo, corpo, linhas, _complemento(chave, t)))

        for j, (rotulo, corpo, linhas, extra) in enumerate(celulas):
            x = MARGEM + j * largura_col
            c.setFont("Helvetica", 6.2)
            c.setFillColor(ROTULO)
            c.drawString(x, y, rotulo.upper())

            c.setFillColor(TINTA)
            for k, linha in enumerate(linhas):
                c.setFont("Helvetica-Bold", corpo)
                c.drawString(x, y - 3.6 * mm - k * entrelinha, linha)

            if extra:
                usado = c.stringWidth(linhas[-1], "Helvetica-Bold", corpo)
                sobra = util - usado
                texto = f" - {extra}"
                cinza = _encolher(c, texto, "Helvetica", 6.2, sobra)
                c.setFont("Helvetica", cinza)
                c.setFillColor(ROTULO)
                c.drawString(x + usado,
                             y - 3.6 * mm - (len(linhas) - 1) * entrelinha, texto)

        maior = max(len(cel[2]) for cel in celulas)
        y -= altura_linha + (maior - 1) * entrelinha

    return y


# ═════════════════════════════════════════════════════════════ fotos
def _desenhar_foto(c, caminho: str, x: float, y: float) -> None:
    """
    Desenha a foto no quadro 4:3 comecando no canto inferior esquerdo (x, y).
    Imagem de outra proporcao e ajustada ao quadro, sem distorcer.
    """
    c.setFillColor(FUNDO_FOTO)
    c.rect(x, y, LARGURA_FOTO, ALTURA_FOTO, stroke=0, fill=1)

    try:
        with PILImage.open(caminho) as im:
            lo, al = im.size
        if lo and al:
            esc = min(LARGURA_FOTO / lo, ALTURA_FOTO / al)
            w, h = lo * esc, al * esc
            c.drawImage(caminho, x + (LARGURA_FOTO - w) / 2,
                        y + (ALTURA_FOTO - h) / 2, width=w, height=h,
                        preserveAspectRatio=True, anchor="c")
    except Exception:                                         # noqa: BLE001
        c.setFillColor(ROTULO)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x + LARGURA_FOTO / 2, y + ALTURA_FOTO / 2,
                            "imagem indisponível")

    c.setStrokeColor(MOLDURA_FOTO)
    c.setLineWidth(0.5)
    c.rect(x, y, LARGURA_FOTO, ALTURA_FOTO, stroke=1, fill=0)


def _grade_fotos(c, t: Transito, codigos: list[str], y: float) -> float:
    """
    Ate 4 fotos, duas por linha, ancoradas logo abaixo do rotulo da secao.

    Nao centralizamos na vertical de proposito: com uma linha so as fotos
    desciam para o meio da folha e o rotulo ficava orfao la em cima. Com o
    topo fixo, a foto sai do mesmo tamanho e na mesma altura em todo laudo,
    e a folga fica embaixo — que e onde um documento normalmente termina.
    Devolve o Y final.
    """
    y -= 4.4 * mm
    for i in range(0, len(codigos), COLUNAS_FOTO):
        linha = codigos[i:i + COLUNAS_FOTO]
        topo = y
        for j, codigo in enumerate(linha):
            img = t.imagem(codigo)
            if img is None or not img.caminho_local:
                continue
            x = MARGEM + j * (LARGURA_FOTO + CALHA)
            _desenhar_foto(c, img.caminho_local, x, topo - ALTURA_FOTO)

            legenda = f"{P.ANGULOS.get(img.angulo, img.angulo)} · {img.nome_arquivo}"
            corpo = _encolher(c, legenda, "Helvetica", 6.2, LARGURA_FOTO)
            c.setFont("Helvetica", corpo)
            c.setFillColor(ROTULO)
            c.drawString(x, topo - ALTURA_FOTO - 3 * mm, legenda)
        y = topo - ALTURA_FOTO - ALTURA_LEGENDA - ESPACO_LINHA
    return y


# ═════════════════════════════════════════════════════════════ rodape
def _rodape(c, pagina: int, total: int) -> None:
    y = MARGEM + 14 * mm
    c.setStrokeColor(FINA)
    c.setLineWidth(0.4)
    c.line(MARGEM, y + 6.5 * mm, LARGURA - MARGEM, y + 6.5 * mm)

    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(TINTA)
    c.drawString(MARGEM, y + 2.6 * mm, f"Emitido por {P.CONCESSIONARIA_RAZAO}")

    c.setFont("Helvetica", 6.8)
    c.setFillColor(ROTULO)
    for i, trecho in enumerate(_quebrar(c, P.DECLARACAO_RODAPE, "Helvetica",
                                        6.8, LARGURA_UTIL)):
        c.drawString(MARGEM, y - 1.2 * mm - i * 3.2 * mm, trecho)

    c.setFont("Helvetica", 7)
    c.setFillColor(TINTA)
    c.drawCentredString(LARGURA / 2, MARGEM - 1 * mm,
                        f"Página {pagina} de {total}")


def _quebrar(c, texto: str, fonte: str, corpo: float, largura: float,
             max_linhas: int | None = None) -> list[str]:
    palavras = texto.split()
    linhas, atual = [], ""
    for p in palavras:
        tentativa = f"{atual} {p}".strip()
        if c.stringWidth(tentativa, fonte, corpo) <= largura:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)

    if max_linhas is not None and len(linhas) > max_linhas:
        # o resto vai junto na ultima linha permitida: ela vai estourar a
        # largura, e e assim que _ajustar percebe que precisa encolher mais
        linhas = linhas[:max_linhas - 1] + [" ".join(linhas[max_linhas - 1:])]
    return linhas


# ═════════════════════════════════════════════════════════════ pagina
def _pagina(c, t: Transito, rel: Relatorio, modulo: str,
            codigos: list[str], numero: int, total: int) -> None:
    y = _cabecalho(c, modulo, rel)

    c.setFont("Helvetica", 6.8)
    c.setFillColor(ROTULO)
    c.drawString(MARGEM, y - 4.6 * mm, linha_analise(rel.metadados))

    y = _rotulo_secao(c, y - 11 * mm, "Dados")
    y = _bloco_dados(c, t, y)

    y = _rotulo_secao(c, y - 2.5 * mm, "Evidência fotográfica")
    if codigos:
        _grade_fotos(c, t, codigos, y)
    else:
        c.setFont("Helvetica", 8)
        c.setFillColor(ROTULO)
        c.drawString(MARGEM, y - 8 * mm,
                     "Nenhuma imagem selecionada para este trânsito.")

    _rodape(c, numero, total)


# ═════════════════════════════════════════════════════════════ gerar
def gerar(t: Transito, rel: Relatorio, modulo: str, pasta_saida: str) -> str:
    """Escreve o PDF de um transito e devolve o caminho."""
    os.makedirs(pasta_saida, exist_ok=True)
    caminho = os.path.join(pasta_saida, nome_arquivo(t, modulo))

    selecionadas = t.selecao_ordenada()[:P.MAX_FOTOS]

    # Antes de desenhar: as fotos escolhidas ainda existem em disco?
    # O desenho tem um plano B que escreve "imagem indisponivel" no quadro —
    # util para nao derrubar a pagina, pessimo se ninguem for avisado. Um
    # relatorio com quadro vazio seguiria calado para a PRF.
    sumidas = [c for c in selecionadas
               if not (t.imagem(c) and t.imagem(c).caminho_local
                       and os.path.isfile(t.imagem(c).caminho_local))]
    if sumidas:
        raise ValueError(
            "as imagens %s não estão mais no cache — refaça a busca deste "
            "trânsito antes de gerar" % ", ".join(sumidas))
    paginas = [selecionadas[i:i + P.FOTOS_POR_PAGINA]
               for i in range(0, len(selecionadas), P.FOTOS_POR_PAGINA)]
    paginas = paginas[:P.MAX_PAGINAS] or [[]]

    c = rl_canvas.Canvas(caminho, pagesize=A4)
    c.setTitle(f"{P.MODULOS[modulo]['titulo_laudo']} — {t.id}")
    c.setAuthor(P.CONCESSIONARIA_RAZAO)

    for n, codigos in enumerate(paginas, start=1):
        _pagina(c, t, rel, modulo, codigos, n, len(paginas))
        c.showPage()
    c.save()
    return caminho


def gerar_todos(rel: Relatorio, modulo: str, pasta_saida: str,
                progresso=None) -> tuple[list[str], list[dict]]:
    """
    Gera o laudo de cada transito autuado.

    Falha em um nao interrompe os demais (RNF-10): devolve
    (caminhos gerados, lista de falhas).
    """
    gerados: list[str] = []
    falhas: list[dict] = []
    autuados = rel.autuados

    for i, t in enumerate(autuados, start=1):
        try:
            gerados.append(gerar(t, rel, modulo, pasta_saida))
            erro = None
        except Exception as e:                                # noqa: BLE001
            erro = str(e)
            falhas.append({"id": t.id, "placa": t.placa, "erro": erro})
        if progresso:
            progresso(i, len(autuados), t, erro)

    return gerados, falhas
