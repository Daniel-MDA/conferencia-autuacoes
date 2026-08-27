"""
Todos os parametros da aplicacao, em um lugar so.

RN-18 / RF-52: nao existe tela de configuracao. Quem mantem a aplicacao muda
aqui, recompila e entrega. Nada abaixo e lido de arquivo externo, com uma
excecao deliberada: a LOGO, que e um binario e fica ao lado do executavel.
"""
from __future__ import annotations

import os
import sys

VERSAO = "2.1"
APP_NOME = "Conferência de Autuações"


# ══════════════════════════════════════════════════ servidor de imagens
SERVIDOR = "10.0.0.11"
PROTOCOLO = "http"
RAIZ_FOTOS = "PHOTOS//"          # a barra dupla reproduz o caminho do servidor
VERIFICAR_CERTIFICADO = False
TIMEOUT_SEGUNDOS = 12
DOWNLOADS_PARALELOS = 8

#: quantos transitos a frente e atras do visivel sao buscados por antecipacao
JANELA_ANTECIPACAO = 3


# ══════════════════════════════════════════════════════════════ angulos
#: Letra -> nome por extenso. A ordem deste dicionario e a ordem de exibicao.
ANGULOS = {
    "F": "Frontal",
    "P": "Panorâmica",
    "L": "Lateral",
    "T": "Traseira",
}
ORDEM_ANGULOS = ["F", "P", "L", "T"]

#: RN-06 — em motocicleta a traseira assume o papel da frontal.
ORDEM_ANGULOS_MOTO = ["T", "P", "F", "L"]

#: RF-12 — quantas tomadas sondar por angulo (F01, F02, F03...).
MAX_TOMADAS = 3

#: RN-05 — o angulo que identifica a placa, por tipo de veiculo.
ANGULO_PLACA = "F"
ANGULO_PLACA_MOTO = "T"
ANGULO_FAIXA = "P"


# ═══════════════════════════════════════════════════════ limites do laudo
MIN_FOTOS = 2            # RN-03
MAX_FOTOS = 8            # RN-04
FOTOS_POR_PAGINA = 4     # RN-04
MAX_PAGINAS = 2          # RN-04


# ══════════════════════════════════════════════════════════════ modulos
MODULOS = {
    "contramao": {
        "nome": "Contramão",
        "titulo_laudo": "Comprovação de Trânsito - Contramão",
        "prefixo_arquivo": "CONTRAMAO",
        "descricao": "Veículo no sentido oposto ao da faixa.",
    },
    "acostamento": {
        "nome": "Acostamento",
        "titulo_laudo": "Comprovação de Trânsito - Acostamento",
        "prefixo_arquivo": "ACOSTAMENTO",
        "descricao": "Veículo fora das faixas de rolamento.",
    },
}


# ═══════════════════════════════════════════════ motivos de descarte (RN-07)
#: A lista e a mesma nos dois modulos.
MOTIVOS_DESCARTE = [
    "Veículo de emergência",
    "Pedestre / ciclista",
    "Veículo sem placa",
    "Placa não identificada",
    "Sem registro fotográfico",
    "Veículo na faixa correta",
    "Alteração na faixa de tráfego",
    "Outros (descreva)",
]
#: exige o campo livre preenchido
MOTIVO_LIVRE = "Outros (descreva)"
#: sugerido quando o transito nao tem nenhuma imagem
MOTIVO_SEM_FOTO = "Sem registro fotográfico"


# ══════════════════════════════════════════════════════════════ o laudo
CONCESSIONARIA_RAZAO = "Concessionária Rodovia Exemplo S.A."
RODOVIA = "BR-000"
ARQUIVO_LOGO = "logo.png"

DECLARACAO_RODAPE = (
    "Este documento é apenas uma evidência fotográfica do tráfego registrado "
    "pelas câmeras do Free-flow, não sendo a concessionária responsável por "
    "emissão da autuação."
)

#: RF-41 — nove campos, tres linhas de tres.
CAMPOS_LAUDO = [
    ("Data", "data"), ("Hora", "hora"), ("ID", "id"),
    ("Rodovia", "rodovia"), ("Praça", "praca"), ("Pista", "pista"),
    ("Placa", "placa"), ("Categoria", "categoria"), ("Velocidade", "velocidade"),
]

#: proporcao fixa das fotos no laudo e na tela (RF-18, RF-42)
PROPORCAO_FOTO = (4, 3)


# ══════════════════════════════════════════════ colunas do relatorio
#: campo interno -> possiveis cabecalhos na planilha, ja normalizados
#: (minusculas, sem acento). O primeiro que casar vence.
#: RF-09: coluna ausente nao quebra a carga; o campo sai vazio.
COLUNAS = {
    "id":         ["id transacao"],
    "data_hora":  ["data/hora", "data / hora", "data hora"],
    "conces":     ["conces.", "conces", "concessionaria"],
    "praca":      ["praca"],
    "pista":      ["pista"],
    "faixa":      ["faixa"],
    "direcao":    ["direcao", "sentido"],
    "placa":      ["placa"],
    "placa_ocr":  ["placa ocr"],
    "categoria":  ["categoria - arr.", "categoria - arr", "categoria"],
    "velocidade": ["vel.", "vel", "velocidade"],
    "modo":       ["modo"],
    "estado":     ["estado"],
    "status":     ["status"],
    "t_pago":     ["t.pago", "t. pago"],
    "f_pago":     ["f.pago", "f. pago"],
    "tipo_anom":  ["tipo anom.", "tipo anom"],
}

#: texto que marca a linha de cabecalho da tabela (RF-05)
MARCA_CABECALHO = "id trans"
#: linha que encerra a tabela
MARCA_FIM = "total"
#: ate onde procurar o cabecalho
LIMITE_BUSCA_CABECALHO = 300

#: valores de Categoria que indicam motocicleta (RN-05/RN-06)
MARCAS_MOTO = ["moto"]

#: valor de Direcao que sinaliza contramao — usado so para ordenar (RF-25)
VALOR_CONTRAMAO = "contramao"


# ══════════════════════════════════════════════════════════════ saida
#: pasta base das remessas. {docs} vira a pasta Documentos do usuario.
PASTA_REMESSAS = "{docs}/Autuacoes"

#: nome da pasta de cada remessa (RN-14)
MOLDE_PASTA_REMESSA = "{modulo}_{data}_v{versao}"

#: nome do laudo (RN-08)
MOLDE_NOME_LAUDO = "{modulo}_{placa}_{id}.pdf"

NOME_INDICE = "indice.csv"
NOME_ZIP = "remessa.zip"
NOME_AUDITORIA = "auditoria.csv"


# ══════════════════════════════════════════════════════════════ janela
LARGURA_JANELA = 1360
ALTURA_JANELA = 940
LARGURA_MINIMA = 1100
ALTURA_MINIMA = 700


# ══════════════════════════════════════════════════════════ diagnostico
#: true = gera imagens sinteticas em vez de acessar o servidor (RF-55).
#: Ligado por `--demo` na linha de comando, nunca pela interface.
MODO_DEMONSTRACAO = False


# ─────────────────────────────────────────────────────────── caminhos
def pasta_do_executavel() -> str:
    """Onde fica a logo. Funciona empacotado e rodando do fonte."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pasta_de_recursos() -> str:
    """Onde ficam os arquivos da interface (embutidos no executavel)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS                                   # type: ignore
    return os.path.dirname(os.path.abspath(__file__))


def caminho_logo() -> str | None:
    alvo = os.path.join(pasta_do_executavel(), ARQUIVO_LOGO)
    return alvo if os.path.isfile(alvo) else None


def pasta_documentos() -> str:
    for nome in ("Documents", "Documentos"):
        alvo = os.path.join(os.path.expanduser("~"), nome)
        if os.path.isdir(alvo):
            return alvo
    return os.path.expanduser("~")


def pasta_remessas() -> str:
    return os.path.normpath(PASTA_REMESSAS.format(docs=pasta_documentos()))


# ────────────────────────────────────────────────────── valores reais
# Este arquivo fica no repositorio publico com valores de exemplo. Quem
# mantem a implantacao real cria autuacao/parametros_local.py (fora do
# git, ver .gitignore) sobrescrevendo SERVIDOR / CONCESSIONARIA_RAZAO /
# RODOVIA / etc. Sem esse arquivo, roda com os valores de exemplo acima.
try:
    from .parametros_local import *  # noqa: F401,F403
except ImportError:
    pass
