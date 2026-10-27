"""Testes do modelo DINA sobre os estados de conhecimento viáveis."""

import random

import pytest

from app.config import CHUTE, DESLIZE, PRIORI, SEMENTE
from app.motor.modelo import atualizar, crenca_inicial, estado_apos, prob_acerto
from conftest import espaco_de

LIVRES = espaco_de("a", "b", "c", "d")          # sem pré-requisitos: conceitos independentes
CADEIA = espaco_de("a", ("b", "a"), ("c", "b"))  # a -> b -> c


def _crencas_aleatorias(espaco, n: int = 100):
    rng = random.Random(SEMENTE)
    for _ in range(n):
        yield crenca_inicial(espaco, {c: rng.uniform(0.02, 0.98) for c in espaco.conceitos})


def _item_aleatorio(rng: random.Random, conceitos: list[str]) -> list[str]:
    return rng.sample(conceitos, rng.randint(1, min(3, len(conceitos))))


# --- Estados viáveis ---

def test_grafo_real_tem_345_estados_viaveis(espaco):
    assert len(espaco.estados) == 345


def test_estados_sao_fechados_por_pre_requisito(espaco, grafo):
    for estado in espaco.estados:
        for c in estado:
            assert set(grafo.prerequisitos(c)) <= estado


def test_cadeia_tem_estados_esperados():
    assert set(CADEIA.estados) == {
        frozenset(), frozenset("a"), frozenset("ab"), frozenset("abc"),
    }


def test_sem_pre_requisitos_todas_as_combinacoes_sao_viaveis():
    assert len(LIVRES.estados) == 2 ** 4


# --- Crença inicial ---

def test_crenca_inicial_sem_pre_requisitos_reproduz_a_priori():
    estado = crenca_inicial(LIVRES).estado
    assert all(p == pytest.approx(PRIORI) for p in estado.values())


def test_crenca_inicial_respeita_o_grafo(espaco, grafo):
    """Quem domina um conceito domina seus pré-requisitos: p nunca é maior que o do pré-requisito."""
    estado = crenca_inicial(espaco).estado
    for c in grafo.conceitos:
        for p in grafo.prerequisitos(c):
            assert estado[c] <= estado[p] + 1e-12


def test_priori_em_cadeia_multiplica_pelos_pre_requisitos():
    estado = crenca_inicial(CADEIA).estado
    assert estado["a"] == pytest.approx(PRIORI)
    assert estado["b"] == pytest.approx(PRIORI ** 2)
    assert estado["c"] == pytest.approx(PRIORI ** 3)


def test_base_do_grafo_comeca_com_a_priori(espaco, grafo):
    """Não dominar a base não é penalizado por cada dependente que fica de fora."""
    assert crenca_inicial(espaco).estado["variavel"] == pytest.approx(PRIORI)


def test_pesos_somam_1(espaco):
    assert sum(crenca_inicial(espaco).pesos) == pytest.approx(1.0)


# --- Probabilidade de acerto ---

def test_sem_pre_requisitos_bate_com_a_formula_dina():
    crenca = crenca_inicial(LIVRES, {"a": 0.8, "b": 0.5, "c": 0.3, "d": 0.5})
    todos = 0.8 * 0.5 * 0.3
    esperado = todos * (1 - DESLIZE) + (1 - todos) * CHUTE
    assert prob_acerto(crenca, ["a", "b", "c"]) == pytest.approx(esperado)


def test_prob_acerto_extremos():
    assert prob_acerto(crenca_inicial(LIVRES, 1.0), ["a"]) == pytest.approx(1 - DESLIZE)
    assert prob_acerto(crenca_inicial(LIVRES, 0.0), ["a"]) == pytest.approx(CHUTE)


def test_conceito_desconhecido_lanca_keyerror():
    with pytest.raises(KeyError, match="desconhecido"):
        prob_acerto(crenca_inicial(LIVRES), ["ponteiro"])


# --- Atualização ---

def test_sem_pre_requisitos_bate_com_bayes_por_conceito():
    """Sem arestas, o modelo é o DINA com conceitos independentes."""
    crenca = crenca_inicial(LIVRES)
    p = PRIORI
    esperado = p * DESLIZE / (p * DESLIZE + (1 - p) * (1 - CHUTE))
    novo = atualizar(crenca, ["a"], False).estado
    assert novo["a"] == pytest.approx(esperado)
    assert novo["b"] == pytest.approx(PRIORI)


@pytest.mark.parametrize("espaco_teste", [LIVRES, CADEIA], ids=["livres", "cadeia"])
def test_acerto_aumenta_e_erro_diminui_p_dos_conceitos_do_item(espaco_teste):
    rng = random.Random(SEMENTE)
    for crenca in _crencas_aleatorias(espaco_teste):
        item = _item_aleatorio(rng, espaco_teste.conceitos)
        antes = crenca.estado
        apos_acerto = atualizar(crenca, item, True).estado
        apos_erro = atualizar(crenca, item, False).estado
        for c in item:
            assert apos_acerto[c] > antes[c]
            assert apos_erro[c] < antes[c]


def test_acertar_um_conceito_aumenta_seus_pre_requisitos():
    crenca = crenca_inicial(CADEIA)
    antes = crenca.estado
    depois = atualizar(crenca, ["c"], True).estado
    assert depois["a"] > antes["a"] and depois["b"] > antes["b"]


def test_errar_um_pre_requisito_derruba_quem_depende_dele():
    crenca = crenca_inicial(CADEIA)
    antes = crenca.estado
    depois = atualizar(crenca, ["a"], False).estado
    assert depois["b"] < antes["b"] and depois["c"] < antes["c"]


def test_atualizar_nao_modifica_a_crenca_original():
    crenca = crenca_inicial(CADEIA)
    pesos, estado = crenca.pesos, crenca.estado
    atualizar(crenca, ["a", "b"], True)
    atualizar(crenca, ["c"], False)
    assert crenca.pesos == pesos
    assert crenca.estado == estado


def test_alterar_o_estado_devolvido_nao_afeta_a_crenca():
    crenca = crenca_inicial(CADEIA)
    estado = crenca.estado
    estado["a"] = 0.0
    assert crenca.estado["a"] != 0.0


def test_probabilidades_ficam_em_0_1_mesmo_apos_muitas_respostas(espaco):
    rng = random.Random(SEMENTE)
    crenca = crenca_inicial(espaco)
    for _ in range(300):
        crenca = atualizar(crenca, _item_aleatorio(rng, espaco.conceitos), rng.random() < 0.5)
        assert all(0.0 <= p <= 1.0 for p in crenca.estado.values())
    assert sum(crenca.pesos) == pytest.approx(1.0)


def test_estado_apos_e_igual_a_atualizar(espaco):
    rng = random.Random(SEMENTE)
    crenca = crenca_inicial(espaco)
    for _ in range(20):
        item = _item_aleatorio(rng, espaco.conceitos)
        acertou = rng.random() < 0.5
        esperado = atualizar(crenca, item, acertou).estado
        obtido = estado_apos(crenca, item, acertou)
        assert obtido == pytest.approx(esperado)
        crenca = atualizar(crenca, item, acertou)


def test_conceito_repetido_no_item_conta_uma_vez():
    crenca = crenca_inicial(LIVRES)
    assert atualizar(crenca, ["a", "a"], True).pesos == atualizar(crenca, ["a"], True).pesos


def test_item_sem_conceitos_e_rejeitado():
    with pytest.raises(ValueError):
        atualizar(crenca_inicial(LIVRES), [], True)
