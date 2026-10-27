"""Fixtures compartilhadas pelos testes."""

import json

import pytest

from app import config
from app.motor.grafo import Grafo, carregar_grafo
from app.motor.modelo import EspacoConhecimento, montar_espaco


@pytest.fixture(scope="session")
def conceitos() -> list[dict]:
    """Conceitos reais de dados/conceitos.json."""
    return json.loads(config.ARQUIVO_CONCEITOS.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def grafo(conceitos: list[dict]) -> Grafo:
    """Grafo montado a partir dos conceitos reais."""
    return carregar_grafo(conceitos)


@pytest.fixture(scope="session")
def espaco(grafo: Grafo) -> EspacoConhecimento:
    """Estados de conhecimento viáveis do grafo real."""
    return montar_espaco(grafo)


@pytest.fixture(scope="session")
def itens() -> list[dict]:
    """Itens reais de dados/itens.json."""
    return json.loads(config.ARQUIVO_ITENS.read_text(encoding="utf-8"))


def espaco_de(*conceitos: tuple[str, ...] | str) -> EspacoConhecimento:
    """Espaço pequeno para testes: 'a' ou ('b', 'a') = b tem a como pré-requisito."""
    lista = []
    for c in conceitos:
        cid, *prereqs = (c,) if isinstance(c, str) else c
        lista.append({"id": cid, "nome": cid, "prerequisitos": prereqs})
    return montar_espaco(carregar_grafo(lista))
