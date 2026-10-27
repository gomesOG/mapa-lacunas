"""Orquestra repositório e motor: é o que as rotas da API chamam.

O banco guarda só as respostas; crença, estado e trilha são sempre recalculados.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app import repositorio as repo
from app.config import LIMIAR_DOMINIO, LIMIAR_LACUNA
from app.db import conectar
from app.motor.diagnostico import (
    LACUNA,
    classificar_conceitos,
    crenca_apos,
    deve_parar,
    diagnosticar,
    erros_por_conceito,
    escolher_proxima,
    reproduzir,
)
from app.motor.grafo import Grafo, carregar_grafo
from app.motor.modelo import Crenca, EspacoConhecimento, montar_espaco
from app.motor.selecao import conceito_em_teste

TAMANHO_MAXIMO_NOME = 80


class NaoEncontrado(Exception):
    """Recurso inexistente (vira HTTP 404)."""


class Conflito(Exception):
    """Operação incompatível com o estado atual (vira HTTP 409)."""


class DadoInvalido(Exception):
    """Entrada recusada (vira HTTP 422)."""


@dataclass
class Conteudo:
    """Conceitos e itens carregados do banco, já prontos para o motor."""

    grafo: Grafo
    espaco: EspacoConhecimento
    conceitos: list[dict]      # em ordem topológica
    itens: list[dict]
    itens_por_id: dict[str, dict]


class Servico:
    """Operações do sistema sobre um arquivo de banco."""

    def __init__(self, caminho_banco: Path | str) -> None:
        self.caminho_banco = Path(caminho_banco)
        self._conteudo: Conteudo | None = None

    # --- Infraestrutura ---

    @contextmanager
    def _conexao(self) -> Iterator[sqlite3.Connection]:
        if not self.caminho_banco.exists():
            raise RuntimeError(
                f"Banco não encontrado em {self.caminho_banco}. Rode: python scripts/criar_banco.py"
            )
        con = conectar(self.caminho_banco)
        try:
            yield con
        finally:
            con.close()

    @property
    def conteudo(self) -> Conteudo:
        """Carrega conceitos e itens na primeira chamada e reaproveita depois."""
        if self._conteudo is None:
            with self._conexao() as con:
                conceitos = repo.listar_conceitos(con)
                itens = repo.listar_itens(con)
            if not conceitos or not itens:
                raise RuntimeError("Banco sem conceitos ou itens. Rode: python scripts/criar_banco.py")
            grafo = carregar_grafo(conceitos)
            por_id = {c["id"]: c for c in conceitos}
            self._conteudo = Conteudo(
                grafo=grafo,
                espaco=montar_espaco(grafo),
                conceitos=[por_id[c] for c in grafo.ordem_topologica()],
                itens=itens,
                itens_por_id={i["id"]: i for i in itens},
            )
        return self._conteudo

    # --- Conceitos ---

    def listar_conceitos(self) -> list[dict]:
        """Conceitos com pré-requisitos, em ordem topológica."""
        return [dict(c) for c in self.conteudo.conceitos]

    # --- Sessão do aluno ---

    def iniciar_sessao(self, nome: str) -> dict:
        """Cria uma sessão para o aluno com esse nome (e o aluno, se ainda não existir)."""
        nome = " ".join(nome.split())
        if not nome:
            raise DadoInvalido("Informe um nome.")
        if len(nome) > TAMANHO_MAXIMO_NOME:
            raise DadoInvalido(f"O nome pode ter no máximo {TAMANHO_MAXIMO_NOME} caracteres.")
        with self._conexao() as con:
            aluno = repo.buscar_aluno_por_nome(con, nome)
            aluno_id = aluno["id"] if aluno else repo.criar_aluno(con, nome)
            sessao_id = repo.criar_sessao(con, aluno_id, _agora())
        return {"sessao_id": sessao_id, "aluno_id": aluno_id}

    def proximo(self, sessao_id: int) -> dict:
        """Próxima questão (sem a resposta correta), ou {'fim': True} se a sessão acabou."""
        with self._conexao() as con:
            sessao = self._sessao(con, sessao_id)
            respostas = repo.listar_respostas(con, sessao_id)
            if sessao["encerrada_em"]:
                return {"fim": True, "n_respondidas": len(respostas)}

            crenca = self._crenca(respostas)
            respondidos = {r["item_id"] for r in respostas}
            erros = self._erros(respostas)
            item, ganho, _ = escolher_proxima(crenca, self.conteudo.itens, respondidos, erros)
            classificacao = classificar_conceitos(crenca.estado, self.conteudo.grafo, erros)
            if item is None or deve_parar(crenca.estado, len(respostas), ganho, classificacao):
                repo.encerrar_sessao(con, sessao_id, _agora())
                return {"fim": True, "n_respondidas": len(respostas)}

        em_teste = conceito_em_teste(crenca.estado, item["conceitos"])
        return {
            "fim": False,
            "ordem": len(respostas) + 1,
            "item": _item_publico(item),
            "conceito_em_teste": {"id": em_teste, "nome": self.conteudo.grafo.nome(em_teste)},
            "ganho": round(ganho, 4),
        }

    def responder(self, sessao_id: int, item_id: str, opcao: int) -> dict:
        """Registra a resposta e devolve se acertou, a explicação e o novo estado."""
        item = self.conteudo.itens_por_id.get(item_id)
        if item is None:
            raise NaoEncontrado(f"Item '{item_id}' não existe.")
        if not 0 <= opcao < len(item["opcoes"]):
            raise DadoInvalido(f"Opção inválida: {opcao}. Use um número de 0 a {len(item['opcoes']) - 1}.")

        with self._conexao() as con:
            sessao = self._sessao(con, sessao_id)
            if sessao["encerrada_em"]:
                raise Conflito("Esta sessão já foi encerrada.")
            respostas = repo.listar_respostas(con, sessao_id)
            if any(r["item_id"] == item_id for r in respostas):
                raise Conflito(f"O item '{item_id}' já foi respondido nesta sessão.")
            acertou = opcao == item["correta"]
            repo.inserir_resposta(con, sessao_id, item_id, opcao, acertou, len(respostas) + 1, _agora())
            respostas = repo.listar_respostas(con, sessao_id)

        return {
            "acertou": acertou,
            "correta": item["correta"],
            "explicacao": item["explicacao"],
            "estado": self._crenca(respostas).estado,
        }

    def diagnostico(self, sessao_id: int) -> dict:
        """Diagnóstico, estado e trilha de raciocínio da sessão."""
        with self._conexao() as con:
            sessao = self._sessao(con, sessao_id)
            aluno = repo.buscar_aluno(con, sessao["aluno_id"])
            respostas = repo.listar_respostas(con, sessao_id)

        crenca, trilha = reproduzir(_pares(respostas), self.conteudo.itens, self.conteudo.espaco)
        for passo, resposta in zip(trilha, respostas):
            item = self.conteudo.itens_por_id[passo["item_id"]]
            passo["conceitos_item"] = list(item["conceitos"])
            passo["enunciado"] = item["enunciado"]
            passo["opcao"] = resposta["opcao"]
        return {
            "sessao": {**sessao, "encerrada": sessao["encerrada_em"] is not None, "n_respondidas": len(respostas)},
            "aluno": _aluno_publico(aluno),
            "diagnostico": diagnosticar(crenca.estado, self.conteudo.grafo, self._erros(respostas)),
            "estado": crenca.estado,
            "trilha": trilha,
            "limiares": _limiares(),
        }

    # --- Turma (professor) ---

    def mapa_turma(self) -> dict:
        """Estado da última sessão de cada aluno, mais os conceitos mais críticos da turma."""
        linhas = self._estados_da_turma()
        alunos = [
            {
                "id": l["aluno"]["id"], "nome": l["aluno"]["nome"], "simulado": l["aluno"]["simulado"],
                "sessao_id": l["sessao_id"], "estado": l["estado"],
                "classificacao": l["diagnostico"]["classificacao"],
            }
            for l in linhas
        ]
        return {
            "conceitos": self.listar_conceitos(),
            "alunos": alunos,
            "criticos": self._criticos(linhas),
            "limiares": _limiares(),
        }

    def risco_turma(self) -> list[dict]:
        """Alunos com alguma lacuna raiz, do que tem mais lacunas para o que tem menos."""
        risco = []
        for l in self._estados_da_turma():
            diag = l["diagnostico"]
            if not diag["lacunas_raiz"]:
                continue
            risco.append({
                "id": l["aluno"]["id"],
                "nome": l["aluno"]["nome"],
                "sessao_id": l["sessao_id"],
                "lacunas_raiz": diag["lacunas_raiz"],
                "lacunas_raiz_nomes": [self.conteudo.grafo.nome(c) for c in diag["lacunas_raiz"]],
                "n_lacunas": sum(1 for v in diag["classificacao"].values() if v == LACUNA),
            })
        return sorted(risco, key=lambda a: (-a["n_lacunas"], -len(a["lacunas_raiz"]), a["nome"].lower()))

    def detalhe_aluno(self, aluno_id: int) -> dict:
        """Dados do aluno e diagnóstico completo da última sessão com respostas."""
        with self._conexao() as con:
            aluno = repo.buscar_aluno(con, aluno_id)
            if aluno is None:
                raise NaoEncontrado(f"Aluno {aluno_id} não existe.")
            sessao = repo.ultima_sessao_com_respostas(con, aluno_id)
        if sessao is None:
            return {"aluno": _aluno_publico(aluno), "ultima_sessao": None}
        return {"aluno": _aluno_publico(aluno), "ultima_sessao": self.diagnostico(sessao["id"])}

    # --- Auxiliares ---

    def _sessao(self, con: sqlite3.Connection, sessao_id: int) -> dict:
        sessao = repo.buscar_sessao(con, sessao_id)
        if sessao is None:
            raise NaoEncontrado(f"Sessão {sessao_id} não existe.")
        return sessao

    def _crenca(self, respostas: list[dict]) -> Crenca:
        return crenca_apos(_pares(respostas), self.conteudo.itens, self.conteudo.espaco)

    def _erros(self, respostas: list[dict]) -> dict[str, int]:
        """Erros por conceito nas questões respondidas (ver erros_por_conceito)."""
        pares = [(self.conteudo.itens_por_id[r["item_id"]], bool(r["acertou"])) for r in respostas]
        return erros_por_conceito(pares, self.conteudo.grafo)

    def _estados_da_turma(self) -> list[dict]:
        """Para cada aluno com respostas: aluno, sessão usada, estado e diagnóstico."""
        with self._conexao() as con:
            pares = []
            for aluno in repo.listar_alunos(con):
                sessao = repo.ultima_sessao_com_respostas(con, aluno["id"])
                if sessao is not None:
                    pares.append((aluno, sessao["id"], repo.listar_respostas(con, sessao["id"])))
        linhas = []
        for aluno, sessao_id, respostas in pares:
            estado = self._crenca(respostas).estado
            linhas.append({
                "aluno": aluno, "sessao_id": sessao_id, "estado": estado,
                "diagnostico": diagnosticar(estado, self.conteudo.grafo, self._erros(respostas)),
            })
        return linhas

    def _criticos(self, linhas: list[dict]) -> list[dict]:
        """Percentual de alunos com lacuna em cada conceito, do maior para o menor."""
        total = len(linhas)
        criticos = []
        for c in self.conteudo.conceitos:
            com_lacuna = sum(1 for l in linhas if l["diagnostico"]["classificacao"][c["id"]] == LACUNA)
            criticos.append({
                "conceito": c["id"], "nome": c["nome"], "alunos_com_lacuna": com_lacuna,
                "percentual": round(100 * com_lacuna / total, 1) if total else 0.0,
            })
        return sorted(criticos, key=lambda x: -x["percentual"])


def _pares(respostas: list[dict]) -> list[tuple[str, bool]]:
    return [(r["item_id"], bool(r["acertou"])) for r in respostas]


def _item_publico(item: dict) -> dict:
    """Item como o aluno pode ver: sem 'correta' e sem 'explicacao'."""
    return {k: item[k] for k in ("id", "enunciado", "codigo", "opcoes", "conceitos")}


def _aluno_publico(aluno: dict) -> dict:
    return {
        "id": aluno["id"], "nome": aluno["nome"], "simulado": bool(aluno["simulado"]),
        "lacuna_plantada": aluno["lacuna_plantada"],
    }


def _limiares() -> dict:
    return {"dominio": LIMIAR_DOMINIO, "lacuna": LIMIAR_LACUNA}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")
