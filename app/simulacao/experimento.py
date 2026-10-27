"""Roda sessões com alunos simulados e mede se o motor encontra a lacuna plantada."""

from __future__ import annotations

import random

from app.config import CHUTE, DESLIZE, SEMENTE
from app.motor.diagnostico import (
    classificar_conceitos,
    deve_parar,
    diagnosticar,
    erros_por_conceito,
    escolher_proxima,
)
from app.motor.modelo import EspacoConhecimento, atualizar, crenca_inicial
from app.motor.selecao import escolher_item_aleatorio
from app.simulacao.gerador import aluno_sem_lacuna, gerar_aluno, responder

ALUNOS_POR_CONCEITO = 20
ALUNOS_SEM_LACUNA = 60   # grupo extra, para medir lacunas falsas

CONFIGURACOES = [
    {"nome": "A", "selecao": "adaptativa", "deslize": DESLIZE, "chute": CHUTE},
    {"nome": "B", "selecao": "aleatoria", "deslize": DESLIZE, "chute": CHUTE},
    {"nome": "C", "selecao": "adaptativa", "deslize": 0.15, "chute": 0.30},
]


def simular_sessao(
    dominio_real: dict[str, int],
    itens: list[dict],
    espaco: EspacoConhecimento,
    rng_respostas: random.Random,
    rng_selecao: random.Random | None = None,
    deslize: float = DESLIZE,
    chute: float = CHUTE,
) -> dict:
    """Simula uma sessão completa até o critério de parada.

    Com rng_selecao=None a seleção é adaptativa (escolher_proxima, que inclui confirmar
    lacunas); caso contrário, aleatória. O critério de parada é o mesmo nos dois casos.
    O motor sempre usa os parâmetros de config.py; deslize/chute são os do aluno simulado.
    """
    grafo = espaco.grafo
    crenca = crenca_inicial(espaco)
    respostas: list[tuple[dict, bool]] = []
    while True:
        respondidos = {item["id"] for item, _ in respostas}
        erros = erros_por_conceito(respostas, grafo)
        melhor, melhor_ganho, _ = escolher_proxima(crenca, itens, respondidos, erros)
        classificacao = classificar_conceitos(crenca.estado, grafo, erros)
        if melhor is None or deve_parar(crenca.estado, len(respostas), melhor_ganho, classificacao):
            break
        if rng_selecao is None:
            item = melhor
        else:
            item = escolher_item_aleatorio(itens, respondidos, rng_selecao)
        acertou = responder(dominio_real, item["conceitos"], rng_respostas, deslize, chute)
        crenca = atualizar(crenca, item["conceitos"], acertou)
        respostas.append((item, acertou))
    return {
        "estado": crenca.estado,
        "respondidos": [item["id"] for item, _ in respostas],
        "diagnostico": diagnosticar(crenca.estado, grafo, erros_por_conceito(respostas, grafo)),
    }


def rodar_configuracao(
    configuracao: dict,
    espaco: EspacoConhecimento,
    itens: list[dict],
    alunos_por_conceito: int = ALUNOS_POR_CONCEITO,
    alunos_sem_lacuna: int = ALUNOS_SEM_LACUNA,
    semente: int = SEMENTE,
) -> list[dict]:
    """Roda alunos_por_conceito alunos para cada conceito, mais alunos_sem_lacuna alunos
    que dominam tudo, e devolve uma linha por aluno."""
    grafo = espaco.grafo
    plano = [c for c in grafo.conceitos for _ in range(alunos_por_conceito)]
    plano += [None] * alunos_sem_lacuna

    linhas = []
    for numero, lacuna in enumerate(plano, start=1):
        # Mesma semente por aluno em todas as configurações: o aluno n tem a mesma lacuna
        # e a mesma sequência de "sorte" em A, B e C.
        rng_respostas = random.Random(semente * 100_000 + numero)
        rng_selecao = (
            random.Random(semente * 100_000 + numero + 50_000)
            if configuracao["selecao"] == "aleatoria" else None
        )
        aluno = aluno_sem_lacuna(grafo) if lacuna is None else gerar_aluno(grafo, rng_respostas, lacuna=lacuna)
        sessao = simular_sessao(
            aluno["dominio"], itens, espaco, rng_respostas, rng_selecao,
            configuracao["deslize"], configuracao["chute"],
        )
        linhas.append(_linha(configuracao["nome"], numero, lacuna, sessao))
    return linhas


def _linha(nome_config: str, numero: int, lacuna: str | None, sessao: dict) -> dict:
    raizes = sessao["diagnostico"]["lacunas_raiz"]
    return {
        "configuracao": nome_config,
        "aluno": numero,
        "lacuna_plantada": lacuna,
        "lacunas_raiz": raizes,
        "situacao": sessao["diagnostico"]["situacao"],
        "n_questoes": len(sessao["respondidos"]),
        # Para quem não tem lacuna, acertar é não apontar nenhuma.
        "acerto_top1": raizes[:1] == [lacuna] if lacuna else not raizes,
        "acerto_top2": lacuna in raizes[:2] if lacuna else not raizes,
    }


def resumir(linhas: list[dict]) -> dict:
    """Métricas agregadas de uma configuração (ou de um conceito).

    Acerto, questões e inconclusivo são medidos nos alunos COM lacuna plantada.
    Nos alunos sem lacuna mede-se a taxa de lacuna falsa: quantos saem com alguma lacuna raiz.
    """
    com = [l for l in linhas if l["lacuna_plantada"]]
    sem = [l for l in linhas if not l["lacuna_plantada"]]
    if not com:
        raise ValueError("Não há alunos com lacuna plantada para resumir")
    n = len(com)
    return {
        "n": n,
        "acerto_top1": sum(l["acerto_top1"] for l in com) / n,
        "acerto_top2": sum(l["acerto_top2"] for l in com) / n,
        "media_questoes": sum(l["n_questoes"] for l in com) / n,
        "taxa_inconclusivo": sum(l["situacao"] == "inconclusivo" for l in com) / n,
        "n_sem_lacuna": len(sem),
        "taxa_lacuna_falsa": sum(bool(l["lacunas_raiz"]) for l in sem) / len(sem) if sem else None,
    }


def resumir_por_conceito(linhas: list[dict], conceitos: list[str]) -> dict[str, dict]:
    """Métricas separadas pela lacuna plantada, para investigar onde o motor erra."""
    return {
        c: resumir([l for l in linhas if l["lacuna_plantada"] == c])
        for c in conceitos
        if any(l["lacuna_plantada"] == c for l in linhas)
    }
