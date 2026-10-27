"""Testes da seleção da próxima questão."""

import random

import pytest

from app.config import SEMENTE
from app.motor.modelo import atualizar, crenca_inicial
from app.motor.selecao import (
    conceito_em_teste,
    entropia,
    escolher_item,
    escolher_item_aleatorio,
    ganho_esperado,
)
from conftest import espaco_de

LIVRES = espaco_de("meio", "baixo", "alto", "x")


def _item(iid: str, *conceitos: str) -> dict:
    return {"id": iid, "conceitos": list(conceitos)}


def _crenca(**p: float):
    base = {c: 0.5 for c in LIVRES.conceitos}
    base.update(p)
    return crenca_inicial(LIVRES, base)


def test_entropia_extremos_e_maximo():
    assert entropia(0.0) == 0.0
    assert entropia(1.0) == 0.0
    assert entropia(0.5) == pytest.approx(1.0)


def test_ganho_esperado_nunca_negativo(espaco):
    rng = random.Random(SEMENTE)
    crenca = crenca_inicial(espaco)
    for _ in range(60):
        item = rng.sample(espaco.conceitos, rng.randint(1, 3))
        assert ganho_esperado(crenca, item) >= 0.0
        crenca = atualizar(crenca, item, rng.random() < 0.5)


def test_ganho_nunca_negativo_com_p_nos_extremos():
    crenca = _crenca(meio=1.0, baixo=0.0)
    for item in (["meio"], ["baixo"], ["meio", "baixo"], ["alto"]):
        assert ganho_esperado(crenca, item) >= 0.0


def test_p_perto_de_meio_tem_mais_ganho_que_perto_dos_extremos():
    crenca = _crenca(meio=0.5, baixo=0.03, alto=0.97)
    assert ganho_esperado(crenca, ["meio"]) > ganho_esperado(crenca, ["baixo"])
    assert ganho_esperado(crenca, ["meio"]) > ganho_esperado(crenca, ["alto"])


def test_conceito_ja_certo_nao_traz_ganho():
    crenca = _crenca(alto=1.0, baixo=0.0)
    assert ganho_esperado(crenca, ["alto"]) == pytest.approx(0.0, abs=1e-12)
    assert ganho_esperado(crenca, ["baixo"]) == pytest.approx(0.0, abs=1e-12)


def test_ganho_considera_o_grafo():
    """Na cadeia a -> b -> c, testar b informa sobre a e c também: rende mais que um conceito isolado."""
    cadeia = espaco_de("a", ("b", "a"), ("c", "b"), "solto")
    crenca = crenca_inicial(cadeia)
    assert ganho_esperado(crenca, ["b"]) > ganho_esperado(crenca, ["solto"])


def test_escolher_item_pula_respondidos():
    crenca = _crenca(meio=0.5, alto=0.9)
    itens = [_item("q1", "meio"), _item("q2", "alto")]
    item, _ = escolher_item(crenca, itens, respondidos={"q1"})
    assert item["id"] == "q2"


def test_escolher_item_sem_itens_disponiveis():
    itens = [_item("q1", "meio")]
    assert escolher_item(_crenca(), itens, respondidos={"q1"}) == (None, 0.0)


def test_escolher_item_devolve_o_ganho_do_item_escolhido():
    crenca = _crenca(meio=0.5, alto=0.95)
    itens = [_item("q1", "alto"), _item("q2", "meio")]
    item, ganho = escolher_item(crenca, itens, set())
    assert item["id"] == "q2"
    assert ganho == pytest.approx(ganho_esperado(crenca, ["meio"]))


def test_desempate_pelo_menor_id_em_ordem_natural():
    itens = [_item("q10", "meio"), _item("q2", "meio")]
    item, _ = escolher_item(_crenca(), itens, set())
    assert item["id"] == "q2"


def test_desempate_pelo_item_com_menos_conceitos():
    # 'alto' já é certo (p = 1), então {meio, alto} informa exatamente o mesmo que {meio}.
    crenca = _crenca(alto=1.0)
    itens = [_item("q1", "meio", "alto"), _item("q2", "meio")]
    item, _ = escolher_item(crenca, itens, set())
    assert item["id"] == "q2"


def test_suspeita_desce_para_um_item_puro(espaco):
    """Aluno que domina a base erra o item composto de recursão: o motor separa as hipóteses
    com um item puro de um pré-requisito, em vez de repetir outro item composto."""
    crenca = crenca_inicial(espaco)
    for conceitos in (["condicional"], ["parametro"], ["condicional"], ["parametro"]):
        crenca = atualizar(crenca, conceitos, True)
    crenca = atualizar(crenca, ["recursao", "escopo", "retorno"], False)
    itens = [
        _item("q1", "recursao", "escopo", "retorno"),
        _item("q2", "recursao", "retorno", "condicional"),
        _item("q3", "escopo"),
        _item("q4", "retorno"),
    ]
    item, _ = escolher_item(crenca, itens, respondidos={"q1"})
    assert item["id"] in {"q3", "q4"}


def test_escolha_aleatoria_e_reproduzivel_e_pula_respondidos():
    itens = [_item(f"q{i}", "meio") for i in range(1, 11)]
    respondidos = {"q1", "q2", "q3"}
    seq1 = [escolher_item_aleatorio(itens, respondidos, random.Random(SEMENTE))["id"] for _ in range(5)]
    seq2 = [escolher_item_aleatorio(itens, respondidos, random.Random(SEMENTE))["id"] for _ in range(5)]
    assert seq1 == seq2
    assert not set(seq1) & respondidos


def test_escolha_aleatoria_sem_itens():
    assert escolher_item_aleatorio([_item("q1", "meio")], {"q1"}, random.Random(SEMENTE)) is None


def test_conceito_em_teste_e_o_mais_proximo_de_meio():
    estado = {"recursao": 0.2, "escopo": 0.48, "retorno": 0.9}
    assert conceito_em_teste(estado, ["recursao", "escopo", "retorno"]) == "escopo"
