"""
O estado da sessao de conferencia.

A aplicacao e local e de um operador por vez (RN-01/RN-02): uma sessao e a
combinacao de um arquivo + um modulo. Trocar qualquer um dos dois encerra a
sessao corrente.

Toda decisao e gravada em disco no ato, em duas vias (RN-12):

  * o RASCUNHO, que permite retomar a sessao de onde parou (RF-57/RF-58);
  * a TRILHA DE AUDITORIA, so de acrescimo, que registra quem decidiu o que
    e quando (RF-59).
"""
from __future__ import annotations

import csv
import getpass
import json
import os
import tempfile
import threading
from datetime import datetime

from . import parametros as P
from .dominio import AUTUADO, DESCARTADO, PENDENTE, SEM_EVIDENCIA, Relatorio
from .imagens import Buscador
from .relatorio import ler, linha_analise, resumo_da_carga

ARQUIVO_RASCUNHO = os.path.join(tempfile.gettempdir(), "autuacao_rascunho.json")


def _usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:                                         # noqa: BLE001
        return "desconhecido"


def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


class Sessao:
    def __init__(self):
        self.lock = threading.RLock()
        self.modulo: str | None = None
        self.relatorio: Relatorio | None = None
        self.buscador: Buscador | None = None
        self.indice = 0
        self.iniciada_em: datetime | None = None
        self.operador = _usuario()
        self.simulado = False
        self.versao_remessa = 0
        self.pasta_remessa = ""

    # ════════════════════════════════════════════════════════ abertura
    def iniciar(self, modulo: str, caminho: str) -> dict:
        """Le a planilha e abre a sessao. Levanta RelatorioInvalido."""
        if modulo not in P.MODULOS:
            raise ValueError(f"Módulo desconhecido: {modulo}")

        rel = ler(caminho)

        with self.lock:
            self._encerrar_buscador()
            self.modulo = modulo
            self.relatorio = rel
            self.indice = 0
            self.iniciada_em = datetime.now()
            self.versao_remessa = 0
            self.pasta_remessa = ""
            self.buscador = Buscador(simulado=self.simulado)

        restauradas = self.restaurar_rascunho()
        # o rascunho traz onde o operador parou; retomar no transito 1 seria
        # jogar fora metade do valor de retomar
        self.agendar_imagens(self.indice)

        resumo = resumo_da_carga(rel)
        resumo["restauradas"] = restauradas
        resumo["modulo"] = modulo
        return resumo

    @property
    def aberta(self) -> bool:
        return self.relatorio is not None and self.modulo is not None

    def _encerrar_buscador(self) -> None:
        if self.buscador:
            self.buscador.encerrar(limpar=False)
            self.buscador = None

    # ═══════════════════════════════════════════════════════ imagens
    def agendar_imagens(self, indice: int) -> None:
        with self.lock:
            if not self.relatorio or not self.buscador:
                return
            transitos = self.relatorio.transitos
            self.indice = max(0, min(indice, len(transitos) - 1))
        self.buscador.agendar(transitos, self.indice)

    def rebuscar(self, indice: int) -> None:
        """RF-15 — nova tentativa depois de religar a VPN."""
        with self.lock:
            if not self.relatorio:
                return
            t = self.relatorio.transitos[indice]
            t.imagens = []
            t.imagens_buscadas = False
            t.erro_busca = None
        self.agendar_imagens(indice)

    # ═══════════════════════════════════════════════════════ decisao
    def decidir(self, indice: int, desfecho: str | None,
                motivo: str = "", descricao: str = "") -> dict:
        with self.lock:
            if not self.relatorio:
                raise ValueError("Nenhum relatório carregado.")
            t = self.relatorio.transitos[indice]

            if desfecho == AUTUADO and not t.pode_autuar:
                raise ValueError(t.bloqueio or "Este trânsito não pode ser autuado.")

            if desfecho == DESCARTADO:
                if motivo not in P.MOTIVOS_DESCARTE:
                    raise ValueError("Escolha um motivo da lista.")
                if motivo == P.MOTIVO_LIVRE and not descricao.strip():
                    raise ValueError(
                        f'O motivo "{P.MOTIVO_LIVRE}" exige a descrição preenchida.')

            t.decisao = desfecho
            t.motivo = motivo if desfecho == DESCARTADO else ""
            t.descricao = descricao.strip()[:500] if desfecho == DESCARTADO else ""
            t.decidido_em = _agora() if desfecho else ""
            t.decidido_por = self.operador if desfecho else ""

        self.salvar_rascunho()
        if desfecho:
            self.registrar_auditoria(t, desfecho)
        return self.estado()

    # ═══════════════════════════════════════════════════════ selecao
    def alternar_foto(self, indice: int, codigo: str) -> dict:
        with self.lock:
            if not self.relatorio:
                raise ValueError("Nenhum relatório carregado.")
            t = self.relatorio.transitos[indice]
            if codigo in t.selecionadas:
                t.selecionadas.remove(codigo)
            else:
                if len(t.selecionadas) >= P.MAX_FOTOS:
                    raise ValueError(
                        f"O relatório aceita no máximo {P.MAX_FOTOS} fotos.")
                if t.imagem(codigo) is None:
                    raise ValueError("Essa imagem não existe neste trânsito.")
                t.selecionadas.append(codigo)
            t.selecionadas = t.selecao_ordenada()
        self.salvar_rascunho()
        return self.transito(indice)

    def definir_selecao(self, indice: int, codigos: list[str]) -> dict:
        with self.lock:
            if not self.relatorio:
                raise ValueError("Nenhum relatório carregado.")
            t = self.relatorio.transitos[indice]
            validos = [c for c in codigos if t.imagem(c) is not None]
            t.selecionadas = validos[:P.MAX_FOTOS]
            t.selecionadas = t.selecao_ordenada()
        self.salvar_rascunho()
        return self.transito(indice)

    def selecao_sugerida(self, indice: int) -> dict:
        with self.lock:
            t = self.relatorio.transitos[indice]           # type: ignore
            t.selecionadas = t.selecao_sugerida()
        self.salvar_rascunho()
        return self.transito(indice)

    # ════════════════════════════════════════════════════════ leitura
    def transito(self, indice: int) -> dict:
        with self.lock:
            if not self.relatorio:
                raise ValueError("Nenhum relatório carregado.")
            transitos = self.relatorio.transitos
            if not 0 <= indice < len(transitos):
                raise ValueError("Índice fora do relatório.")
            self.indice = indice
            dados = transitos[indice].resumo()
        self.agendar_imagens(indice)
        dados["indice"] = indice
        return dados

    def estado(self) -> dict:
        with self.lock:
            if not self.relatorio or not self.modulo:
                return {"aberta": False, "modulos": self._modulos(),
                        "rascunho": self.rascunho_disponivel()}

            r = self.relatorio
            estados = [t.estado for t in r.transitos]
            return {
                "aberta": True,
                "modulo": self.modulo,
                "modulo_nome": P.MODULOS[self.modulo]["nome"],
                "titulo_laudo": P.MODULOS[self.modulo]["titulo_laudo"],
                "arquivo": os.path.basename(r.arquivo),
                "linha_analise": linha_analise(r.metadados),
                "concessionaria": r.concessionaria,
                "periodo": r.periodo,
                "operador": self.operador,
                "indice": self.indice,
                "total": len(r.transitos),
                "estados": estados,
                "autuados": estados.count(AUTUADO),
                "descartados": estados.count(DESCARTADO),
                "pendentes": estados.count(PENDENTE),
                "sem_evidencia": estados.count(SEM_EVIDENCIA),
                "buscadas": sum(1 for t in r.transitos if t.imagens_buscadas),
                "aviso_rede": self.buscador.aviso if self.buscador else None,
                "colunas_faltando": r.colunas_faltando,
                "simulado": self.simulado,
                "pasta_remessa": self.pasta_remessa,
            }

    def lista(self) -> dict:
        """
        Placa, hora e ID de cada trânsito — não mudam durante a sessão.

        Fora do estado de propósito: o estado é consultado de segundos em
        segundos e carregar essas três listas junto reenviava dezenas de KB
        a cada volta, num relatório grande.
        """
        with self.lock:
            if not self.relatorio:
                return {"placas": [], "horas": [], "ids": []}
            t = self.relatorio.transitos
            return {
                "placas": [x.placa for x in t],
                "horas": [x.hora for x in t],
                "ids": [x.id for x in t],
            }

    @staticmethod
    def _modulos() -> list[dict]:
        return [{"chave": k, **v} for k, v in P.MODULOS.items()]

    def resumo_final(self) -> dict:
        """O que a tela de resumo mostra (RF-60)."""
        with self.lock:
            if not self.relatorio:
                return {}
            r = self.relatorio
            por_motivo: dict[str, int] = {}
            for t in r.descartados:
                por_motivo[t.motivo] = por_motivo.get(t.motivo, 0) + 1

            autuados = r.autuados
            fotos = sum(len(t.selecao_ordenada()) for t in autuados)
            paginas = sum(t.paginas_laudo for t in autuados)
            return {
                "autuados": len(autuados),
                "descartados": len(r.descartados),
                "pendentes": len(r.pendentes),
                "sem_evidencia": len(r.sem_evidencia),
                "por_motivo": [{"motivo": m, "quantidade": q}
                               for m, q in sorted(por_motivo.items(),
                                                  key=lambda x: -x[1])],
                "fotos": fotos,
                "paginas": paginas,
                "pasta_sugerida": self.pasta_sugerida(),
            }

    def pasta_sugerida(self) -> str:
        if not self.modulo:
            return P.pasta_remessas()
        data = (self.iniciada_em or datetime.now()).strftime("%Y%m%d")
        nome = P.MOLDE_PASTA_REMESSA.format(
            modulo=P.MODULOS[self.modulo]["prefixo_arquivo"],
            data=data, versao=max(1, self.versao_remessa + 1))
        return os.path.join(P.pasta_remessas(), nome)

    # ══════════════════════════════════════════════════════ rascunho
    def _chave(self) -> str:
        if not self.relatorio or not self.modulo:
            return ""
        return f"{os.path.abspath(self.relatorio.arquivo)}|{self.modulo}"

    def salvar_rascunho(self) -> None:
        with self.lock:
            if not self.relatorio or not self.modulo:
                return
            dados = {
                "chave": self._chave(),
                "arquivo": os.path.abspath(self.relatorio.arquivo),
                "modulo": self.modulo,
                "salvo_em": datetime.now().isoformat(timespec="seconds"),
                "indice": self.indice,
                "remessa": self.pasta_remessa,
                "decisoes": {
                    t.id: {"decisao": t.decisao, "motivo": t.motivo,
                           "descricao": t.descricao,
                           "selecionadas": t.selecionadas}
                    for t in self.relatorio.transitos
                    if t.decisao or t.selecionadas
                },
            }
        try:
            with open(ARQUIVO_RASCUNHO, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def restaurar_rascunho(self) -> int:
        dados = self._ler_rascunho()
        if not dados:
            return 0
        with self.lock:
            if not self.relatorio or dados.get("chave") != self._chave():
                return 0
            mapa = dados.get("decisoes", {})
            n = 0
            for t in self.relatorio.transitos:
                info = mapa.get(t.id)
                if not info:
                    continue
                t.decisao = info.get("decisao")
                t.motivo = info.get("motivo", "")
                t.descricao = info.get("descricao", "")
                t.selecionadas = list(info.get("selecionadas") or [])
                if t.decisao:
                    n += 1
            self.indice = min(int(dados.get("indice", 0)),
                              len(self.relatorio.transitos) - 1)
            return n

    @staticmethod
    def _ler_rascunho() -> dict | None:
        if not os.path.exists(ARQUIVO_RASCUNHO):
            return None
        try:
            with open(ARQUIVO_RASCUNHO, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def rascunho_disponivel(self) -> dict | None:
        """RF-03 — a faixa de retomada na tela de modulos."""
        dados = self._ler_rascunho()
        if not dados:
            return None
        arquivo = dados.get("arquivo", "")
        if not arquivo or not os.path.isfile(arquivo):
            return None
        modulo = dados.get("modulo")
        if modulo not in P.MODULOS:
            return None
        decididos = sum(1 for d in dados.get("decisoes", {}).values()
                        if d.get("decisao"))
        salvo = dados.get("salvo_em", "")
        try:
            quando = datetime.fromisoformat(salvo).strftime("%d/%m às %H:%M")
        except ValueError:
            quando = salvo
        return {
            "arquivo": arquivo,
            "nome_arquivo": os.path.basename(arquivo),
            "modulo": modulo,
            "modulo_nome": P.MODULOS[modulo]["nome"],
            "decididos": decididos,
            "quando": quando,
            # sessao que ja virou remessa foi CONCLUIDA, nao interrompida
            "remessa": dados.get("remessa", ""),
        }

    def descartar_rascunho(self) -> None:
        try:
            os.remove(ARQUIVO_RASCUNHO)
        except OSError:
            pass

    # ═════════════════════════════════════════════════════ auditoria
    def caminho_auditoria(self) -> str:
        return os.path.join(P.pasta_remessas(), P.NOME_AUDITORIA)

    def registrar_auditoria(self, t, desfecho: str) -> None:
        """RF-59 — arquivo so de acrescimo."""
        caminho = self.caminho_auditoria()
        try:
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            novo = not os.path.exists(caminho)
            with open(caminho, "a", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, delimiter=";")
                if novo:
                    w.writerow(["data_hora", "operador", "modulo", "arquivo",
                                "id_transito", "placa", "acao", "motivo",
                                "descricao", "fotos"])
                w.writerow([
                    _agora(), self.operador, self.modulo or "",
                    os.path.basename(self.relatorio.arquivo) if self.relatorio else "",
                    t.id, t.placa, desfecho, t.motivo, t.descricao,
                    " ".join(t.selecao_ordenada()),
                ])
        except OSError:
            pass

    # ═══════════════════════════════════════════════════════ encerrar
    def fechar(self) -> None:
        """RN-02 — encerra a sessao corrente, mantendo o rascunho em disco."""
        self.encerrar()
        with self.lock:
            self.relatorio = None
            self.modulo = None
            self.indice = 0
            self.pasta_remessa = ""
            self.versao_remessa = 0

    def encerrar(self) -> None:
        """RN-16 — ao fechar, o cache de imagens vai junto."""
        with self.lock:
            if self.buscador:
                self.buscador.encerrar(limpar=True)
                self.buscador = None


SESSAO = Sessao()
