"""Escolha da próxima questão por ganho de informação esperado.

Módulo puro: sem banco, sem arquivos.
"""

from __future__ import annotations

import math
import random
import re

from app.motor.modelo import Crenca, Estado, estado_apos, prob_acerto


def entropia(p: float) -> float:
    """Entropia binária em bits, com H(0) = H(1) = 0."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def incerteza(estado: Estado) -> float:
    """Soma das entropias de todos os conceitos, em bits."""
    return sum(entropia(p) for p in estado.values())


def ganho_esperado(crenca: Crenca, conceitos_item: list[str]) -> float:
    """Quanto a incerteza sobre TODOS os conceitos deve cair com a resposta, em bits.

    Considera todos os conceitos, e não só os do item, porque pelo grafo uma
    resposta também informa sobre pré-requisitos e dependentes.
    """
    h_antes = incerteza(crenca.estado)
    q = prob_acerto(crenca, conceitos_item)
    h_depois = (
        q * incerteza(estado_apos(crenca, conceitos_item, True))
        + (1.0 - q) * incerteza(estado_apos(crenca, conceitos_item, False))
    )
    # Matematicamente nunca é negativo; o max só absorve erro de arredondamento.
    return max(0.0, h_antes - h_depois)


def itens_disponiveis(itens: list[dict], respondidos: set[str]) -> list[dict]:
    """Itens que ainda não foram respondidos, na ordem original."""
    return [item for item in itens if item["id"] not in respondidos]


def escolher_item(
    crenca: Crenca,
    itens: list[dict],
    respondidos: set[str],
) -> tuple[dict | None, float]:
    """Retorna (item, ganho) com o maior ganho esperado, ou (None, 0.0) se não houver mais itens.

    Desempate: primeiro o item com menos conceitos (mais específico), depois o menor id.
    """
    melhor: dict | None = None
    melhor_chave: tuple | None = None
    melhor_ganho = 0.0
    for item in itens_disponiveis(itens, respondidos):
        ganho = ganho_esperado(crenca, item["conceitos"])
        chave = (-round(ganho, 12), len(item["conceitos"]), _chave_id(item["id"]))
        if melhor_chave is None or chave < melhor_chave:
            melhor, melhor_chave, melhor_ganho = item, chave, ganho
    return melhor, melhor_ganho


def escolher_item_aleatorio(
    itens: list[dict],
    respondidos: set[str],
    rng: random.Random,
) -> dict | None:
    """Linha de base usada na validação: qualquer item ainda não respondido, ao acaso."""
    disponiveis = itens_disponiveis(itens, respondidos)
    return rng.choice(disponiveis) if disponiveis else None


def conceito_em_teste(estado: Estado, conceitos_item: list[str]) -> str:
    """Conceito do item com p mais próximo de 0,5 (o que o item mais ajuda a esclarecer)."""
    return min(conceitos_item, key=lambda c: abs(estado[c] - 0.5))


def _chave_id(item_id: str) -> tuple[str, int]:
    """Ordem natural de ids: q2 vem antes de q10."""
    m = re.fullmatch(r"(.*?)(\d+)", item_id)
    return (m.group(1), int(m.group(2))) if m else (item_id, -1)
