"""
As entidades do dominio. Nenhuma delas sabe o que e HTTP, Excel ou PDF.

Secao 09 do caderno de requisitos.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import parametros as P

#: estados possiveis de um transito
PENDENTE = "pendente"
AUTUADO = "autuado"
DESCARTADO = "descartado"
SEM_EVIDENCIA = "sem_evidencia"


def normalizar(v: Any) -> str:
    """minusculas, sem acento, sem espacos nas pontas."""
    if v is None:
        return ""
    s = str(v).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def texto(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M:%S")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def numero(v: Any) -> str:
    """
    "03", "3", "3.0", "Praça 03" -> "3".

    Praca e faixa aparecem escritas de varios jeitos na planilha; as tabelas
    de PRACAS e FAIXAS sao indexadas pelo numero limpo.
    """
    s = texto(v)
    achado = re.search(r"\d+", s)
    return str(int(achado.group())) if achado else s


# ══════════════════════════════════════════════════════════════ Imagem
@dataclass
class Imagem:
    angulo: str                       # "F"
    tomada: int                       # 1
    url: str
    caminho_local: str | None = None
    erro: str | None = None

    @property
    def codigo(self) -> str:
        """F01, P02, ..."""
        return f"{self.angulo}{self.tomada:02d}"

    @property
    def nome_arquivo(self) -> str:
        return self.url.rsplit("/", 1)[-1] if self.url else ""

    @property
    def ok(self) -> bool:
        return self.caminho_local is not None

    def resumo(self) -> dict:
        return {
            "codigo": self.codigo,
            "angulo": self.angulo,
            "tomada": self.tomada,
            "nome": P.ANGULOS.get(self.angulo, self.angulo),
            "arquivo": self.nome_arquivo,
            "ok": self.ok,
            "erro": self.erro,
            "url": self.url,
        }


# ════════════════════════════════════════════════════════════ Transito
@dataclass
class Transito:
    id: str
    linha: int
    campos: dict[str, Any] = field(default_factory=dict)   # chave interna -> valor

    imagens: list[Imagem] = field(default_factory=list)
    imagens_buscadas: bool = False
    erro_busca: str | None = None
    url_tentada: str = ""        # RF-15 — mostrada no diagnostico da falha

    decisao: str | None = None            # AUTUADO | DESCARTADO | None
    motivo: str = ""
    descricao: str = ""
    selecionadas: list[str] = field(default_factory=list)   # codigos, na ordem
    decidido_em: str = ""
    decidido_por: str = ""

    # ─────────────────────────────────────────────── leitura dos campos
    def campo(self, chave: str) -> str:
        return texto(self.campos.get(chave))

    @property
    def data_hora(self) -> datetime | None:
        v = self.campos.get("data_hora")
        if isinstance(v, datetime):
            return v
        # o proprio ID carrega AAAAMMDDHHMMSS logo apos o prefixo de 9
        bruto = self.id[9:23]
        if len(bruto) == 14 and bruto.isdigit():
            try:
                return datetime.strptime(bruto, "%Y%m%d%H%M%S")
            except ValueError:
                pass
        return None

    @property
    def data(self) -> str:
        d = self.data_hora
        return d.strftime("%d/%m/%Y") if d else ""

    @property
    def hora(self) -> str:
        d = self.data_hora
        return d.strftime("%H:%M:%S") if d else ""

    @property
    def pasta_servidor(self) -> str:
        """
        RN-17 — a pasta das imagens sao os 9 primeiros caracteres do ID.
        Medido em 3.419 transitos: a coluna Pista discorda em 34% dos casos e
        NAO deve ser usada para montar o caminho.
        """
        return self.id[:9]

    @property
    def data_pasta(self) -> str:
        """AAAAMMDD, o nivel de data no caminho do servidor."""
        bruto = self.id[9:17]
        if len(bruto) == 8 and bruto.isdigit():
            return bruto
        d = self.data_hora
        return d.strftime("%Y%m%d") if d else ""

    @property
    def praca(self) -> str:
        na_planilha = self.campo("praca")
        if na_planilha:
            return na_planilha
        return self.id[2:4]

    @property
    def pista(self) -> str:
        """
        A pista vem sempre da coluna Pista da planilha.

        O ID carrega cinco caracteres nessa posicao e eles servem para achar
        a pasta das imagens (ver pasta_servidor) — so para isso. Em 34% dos
        transitos os dois valores discordam, e quem vale no documento e o
        que o Backoffice escreveu na coluna.
        """
        return self.campo("pista")

    @property
    def data_e_hora(self) -> str:
        """"01/08/2026 08:10:30" — as duas numa celula so do laudo."""
        return f"{self.data} {self.hora}".strip()

    # ────────────────────────────────────── onde foi, e para onde ia
    @property
    def _faixa_tabela(self) -> dict:
        return P.FAIXAS.get(numero(self.campo("faixa"))) or {}

    @property
    def praca_completa(self) -> str:
        """"01 - Cidade Exemplo - KM 000,000" — a praca e onde fica (RF-41b)."""
        dados = P.PRACAS.get(numero(self.praca)) or {}
        partes = [self.praca, dados.get("cidade", "")]
        if dados.get("km"):
            partes.append(f"KM {dados['km']}")
        return " - ".join(p for p in partes if p)

    @property
    def faixa(self) -> str:
        """O numero da faixa como sai no documento: dois digitos."""
        n = numero(self.campo("faixa"))
        return n.zfill(2) if n.isdigit() else n

    @property
    def faixa_descrita(self) -> str:
        """"03 - Tráfego" — o numero da faixa e o que ela e."""
        return " - ".join(p for p in (self.faixa,
                                      self._faixa_tabela.get("descricao", "")) if p)

    # RN-19 — pista e sentido abaixo respondem "para onde o veiculo ia",
    # nao "como a faixa e". Em contramao ele ia para o lado contrario, e
    # os dois saem invertidos: a celula descreve o deslocamento.
    @property
    def pista_deslocamento(self) -> str:
        propria = self._faixa_tabela.get("pista", "")
        if propria and self.eh_contramao:
            return P.PISTAS_OPOSTAS.get(propria, propria)
        return propria

    @property
    def sentido(self) -> str:
        proprio = self._faixa_tabela.get("sentido", "")
        if proprio and self.eh_contramao:
            return P.SENTIDOS_OPOSTOS.get(proprio, proprio)
        return proprio

    @property
    def deslocamento(self) -> str:
        """
        "Norte - Crescente (Exemplo A) (contra-mão)"

        O marcador fica porque o titulo do documento nao basta: no modulo
        de acostamento um veiculo tambem pode estar em contramao, e sem
        ele a celula invertida sairia identica a de um veiculo regular
        numa faixa do outro lado. Faixa fora da tabela sai vazia — melhor
        do que inventar um sentido.
        """
        junto = " - ".join(p for p in (self.pista_deslocamento, self.sentido) if p)
        if junto and self.eh_contramao:
            junto += " (contra-mão)"
        return junto

    @property
    def placa(self) -> str:
        return self.campo("placa") or self.campo("placa_ocr")

    @property
    def placa_ocr(self) -> str:
        return self.campo("placa_ocr")

    @property
    def placa_diverge(self) -> bool:
        a, b = self.campo("placa"), self.campo("placa_ocr")
        return bool(a and b and a != b)

    @property
    def categoria(self) -> str:
        return self.campo("categoria")

    @property
    def velocidade(self) -> str:
        return self.campo("velocidade")

    @property
    def eh_moto(self) -> bool:
        cat = normalizar(self.categoria)
        return any(m in cat for m in P.MARCAS_MOTO)

    @property
    def eh_contramao(self) -> bool:
        return normalizar(self.campo("direcao")) == P.VALOR_CONTRAMAO

    @property
    def ordem_angulos(self) -> list[str]:
        return P.ORDEM_ANGULOS_MOTO if self.eh_moto else P.ORDEM_ANGULOS

    @property
    def angulo_placa(self) -> str:
        return P.ANGULO_PLACA_MOTO if self.eh_moto else P.ANGULO_PLACA

    # ─────────────────────────────────────────────────────── imagens
    @property
    def imagens_ok(self) -> list[Imagem]:
        return [i for i in self.imagens if i.ok]

    def ordenar_imagens(self) -> None:
        ordem = self.ordem_angulos
        self.imagens.sort(
            key=lambda i: (ordem.index(i.angulo) if i.angulo in ordem else 99,
                           i.tomada))

    def imagem(self, codigo: str) -> Imagem | None:
        for i in self.imagens:
            if i.codigo == codigo:
                return i
        return None

    def contagem_por_angulo(self) -> dict[str, int]:
        """Quantas fotos existem em cada angulo — vai no numero das abas."""
        cont = {a: 0 for a in self.ordem_angulos}
        for i in self.imagens_ok:
            if i.angulo in cont:
                cont[i.angulo] += 1
        return cont

    # ─────────────────────────────────────────────────────── selecao
    def selecao_sugerida(self) -> list[str]:
        """RN-05 — a que identifica a placa e a panoramica."""
        escolhidas: list[str] = []
        for angulo in (self.angulo_placa, P.ANGULO_FAIXA):
            for img in self.imagens_ok:
                if img.angulo == angulo:
                    escolhidas.append(img.codigo)
                    break
        return escolhidas

    def selecao_ordenada(self) -> list[str]:
        """A selecao na ordem em que sai no laudo (RN-06)."""
        disponiveis = [i.codigo for i in self.imagens_ok]
        self.ordenar_imagens()
        ordenados = [i.codigo for i in self.imagens_ok]
        return [c for c in ordenados
                if c in self.selecionadas and c in disponiveis]

    @property
    def paginas_laudo(self) -> int:
        n = len(self.selecao_ordenada())
        if not n:
            return 0
        return (n + P.FOTOS_POR_PAGINA - 1) // P.FOTOS_POR_PAGINA

    # ─────────────────────────────────────────────────────── estado
    @property
    def estado(self) -> str:
        if self.decisao:
            return self.decisao
        if self.imagens_buscadas and not self.imagens_ok:
            return SEM_EVIDENCIA
        return PENDENTE

    @property
    def bloqueio(self) -> str | None:
        """Por que este transito nao pode ser autuado agora, se for o caso."""
        if not self.imagens_buscadas:
            return "Buscando as imagens…"
        if not self.imagens_ok:
            return "Sem imagem recuperada: não pode ser autuado."
        if len(self.selecao_ordenada()) < P.MIN_FOTOS:
            return (f"Marque ao menos {P.MIN_FOTOS} fotos: placa e panorâmica.")
        return None

    @property
    def pode_autuar(self) -> bool:
        return self.bloqueio is None

    # ─────────────────────────────────────────────────────── laudo
    def nome_laudo(self, modulo: str) -> str:
        placa = re.sub(r"[^A-Za-z0-9]", "", self.placa) or "SEMPLACA"
        return P.MOLDE_NOME_LAUDO.format(
            modulo=P.MODULOS[modulo]["prefixo_arquivo"],
            placa=placa.upper(),
            id=self.id,
        )

    # ────────────────────────────────────────────── para a interface
    def resumo(self) -> dict:
        self.ordenar_imagens()
        return {
            "id": self.id,
            "linha": self.linha,
            "data": self.data,
            "hora": self.hora,
            "praca": self.praca,
            "praca_completa": self.praca_completa,
            "pista": self.pista,
            "faixa": self.faixa,
            "faixa_descrita": self.faixa_descrita,
            "deslocamento": self.deslocamento,
            "direcao": self.campo("direcao"),
            "placa": self.placa,
            "placa_ocr": self.placa_ocr,
            "placa_diverge": self.placa_diverge,
            "categoria": self.categoria,
            "velocidade": self.campo("velocidade"),
            "modo": self.campo("modo"),
            "estado_tr": self.campo("estado"),
            "status": self.campo("status"),
            "t_pago": self.campo("t_pago"),
            "f_pago": self.campo("f_pago"),
            "tipo_anom": self.campo("tipo_anom"),
            "eh_moto": self.eh_moto,
            "eh_contramao": self.eh_contramao,
            "pasta_servidor": self.pasta_servidor,
            "ordem_angulos": self.ordem_angulos,
            "contagem_angulos": self.contagem_por_angulo(),
            "imagens": [i.resumo() for i in self.imagens],
            "imagens_buscadas": self.imagens_buscadas,
            "erro_busca": self.erro_busca,
            "url_tentada": self.url_tentada,
            "selecionadas": self.selecao_ordenada(),
            "decisao": self.decisao,
            "motivo": self.motivo,
            "descricao": self.descricao,
            "estado": self.estado,
            "bloqueio": self.bloqueio,
            "paginas_laudo": self.paginas_laudo,
        }


# ═══════════════════════════════════════════════════════════ Relatorio
@dataclass
class Relatorio:
    arquivo: str
    metadados: dict[str, str] = field(default_factory=dict)
    colunas_achadas: dict[str, str] = field(default_factory=dict)
    colunas_faltando: list[str] = field(default_factory=list)
    transitos: list[Transito] = field(default_factory=list)

    @property
    def autuados(self) -> list[Transito]:
        return [t for t in self.transitos if t.decisao == AUTUADO]

    @property
    def descartados(self) -> list[Transito]:
        return [t for t in self.transitos if t.decisao == DESCARTADO]

    @property
    def pendentes(self) -> list[Transito]:
        return [t for t in self.transitos if t.estado == PENDENTE]

    @property
    def sem_evidencia(self) -> list[Transito]:
        return [t for t in self.transitos if t.estado == SEM_EVIDENCIA]

    @property
    def concessionaria(self) -> str:
        return self.metadados.get("Concessionária", "")

    @property
    def periodo(self) -> str:
        return self.metadados.get("Data", "")

    @property
    def pracas(self) -> list[str]:
        vistas: list[str] = []
        for t in self.transitos:
            if t.praca not in vistas:
                vistas.append(t.praca)
        return sorted(vistas)

    @property
    def pistas(self) -> list[str]:
        # a pista vem da coluna e a coluna pode faltar (RF-09): sem o filtro
        # o resumo da carga mostraria uma pista em branco na lista
        vistas: list[str] = []
        for t in self.transitos:
            if t.pista and t.pista not in vistas:
                vistas.append(t.pista)
        return sorted(vistas)
