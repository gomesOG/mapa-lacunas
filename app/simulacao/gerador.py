"""Alunos simulados com uma lacuna plantada, coerente com o grafo de pré-requisitos."""

from __future__ import annotations

import random

from app.config import CHUTE, DESLIZE
from app.motor.grafo import Grafo


def gerar_aluno(grafo: Grafo, rng: random.Random, lacuna: str | None = None) -> dict:
    """Cria um aluno com domínio real 0/1 por conceito.

    A lacuna plantada (sorteada se não for informada) e todos os seus descendentes
    ficam com 0: ninguém domina recursão sem dominar escopo.
    Retorna {'lacuna': r, 'dominio': {conceito: 0 ou 1}}.
    """
    r = lacuna if lacuna is not None else rng.choice(grafo.conceitos)
    sem_dominio = {r, *grafo.descendentes(r)}
    dominio = {c: 0 if c in sem_dominio else 1 for c in grafo.conceitos}
    return {"lacuna": r, "dominio": dominio}


def aluno_sem_lacuna(grafo: Grafo) -> dict:
    """Aluno que domina todos os conceitos (usado para medir lacunas falsas)."""
    return {"lacuna": None, "dominio": {c: 1 for c in grafo.conceitos}}


def responder(
    dominio_real: dict[str, int],
    conceitos_item: list[str],
    rng: random.Random,
    deslize: float = DESLIZE,
    chute: float = CHUTE,
) -> bool:
    """Sorteia se o aluno simulado acerta o item, pelo modelo DINA com os parâmetros dados."""
    domina_tudo = all(dominio_real[c] == 1 for c in conceitos_item)
    p_acerto = 1.0 - deslize if domina_tudo else chute
    return rng.random() < p_acerto
