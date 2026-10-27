"""Testes de consistência do banco de itens (dados/itens.json)."""

import json
import re

import pytest

from app import config


@pytest.fixture(scope="module")
def itens() -> list[dict]:
    return json.loads(config.ARQUIVO_ITENS.read_text(encoding="utf-8"))


def test_quantidade_de_itens(itens):
    assert 40 <= len(itens) <= 45


def test_ids_unicos_e_no_formato(itens):
    ids = [i["id"] for i in itens]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"q\d+", i) for i in ids)


def test_campos_obrigatorios_preenchidos(itens):
    for item in itens:
        for campo in ("enunciado", "codigo", "explicacao"):
            assert item[campo].strip(), f"{item['id']}: '{campo}' vazio"


def test_quatro_opcoes_distintas(itens):
    for item in itens:
        assert len(item["opcoes"]) == 4, item["id"]
        assert len(set(item["opcoes"])) == 4, item["id"]


def test_correta_entre_0_e_3(itens):
    for item in itens:
        assert isinstance(item["correta"], int) and 0 <= item["correta"] <= 3, item["id"]


def test_codigo_curto(itens):
    for item in itens:
        assert len(item["codigo"].splitlines()) <= 8, item["id"]


def test_de_1_a_3_conceitos_existentes(itens, grafo):
    for item in itens:
        assert 1 <= len(item["conceitos"]) <= 3, item["id"]
        assert len(set(item["conceitos"])) == len(item["conceitos"]), item["id"]
        for c in item["conceitos"]:
            assert c in grafo.conceitos, f"{item['id']}: conceito inexistente '{c}'"


def test_todo_conceito_tem_item_puro(itens, grafo):
    """Regra de identificabilidade: sem item puro o motor não separa um conceito dos outros."""
    puros = {item["conceitos"][0] for item in itens if len(item["conceitos"]) == 1}
    faltando = set(grafo.conceitos) - puros
    assert not faltando, f"Conceitos sem item puro: {sorted(faltando)}"


def test_itens_compostos_combinam_conceito_com_pre_requisitos_diretos(itens, grafo):
    for item in itens:
        if len(item["conceitos"]) == 1:
            continue
        principal, *outros = item["conceitos"]
        assert set(outros) <= set(grafo.prerequisitos(principal)), item["id"]
