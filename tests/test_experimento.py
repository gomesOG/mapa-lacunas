"""Testes do gerador de alunos simulados e do experimento de validação."""

import random

import pytest

from app.config import MAX_QUESTOES, MIN_QUESTOES, SEMENTE
from app.simulacao.experimento import (
    CONFIGURACOES,
    resumir,
    resumir_por_conceito,
    rodar_configuracao,
    simular_sessao,
)
from app.simulacao.gerador import aluno_sem_lacuna, gerar_aluno, responder


# --- Gerador ---

def test_lacuna_plantada_e_descendentes_ficam_sem_dominio(grafo):
    aluno = gerar_aluno(grafo, random.Random(SEMENTE), lacuna="laco")
    sem_dominio = {c for c, v in aluno["dominio"].items() if v == 0}
    assert aluno["lacuna"] == "laco"
    assert sem_dominio == {"laco", "laco_aninhado", "vetor", "busca_vetor", "matriz"}


def test_dominio_coerente_com_o_grafo(grafo):
    """Quem domina um conceito domina todos os seus pré-requisitos."""
    rng = random.Random(SEMENTE)
    for _ in range(50):
        dominio = gerar_aluno(grafo, rng)["dominio"]
        for c in grafo.conceitos:
            if dominio[c] == 1:
                assert all(dominio[p] == 1 for p in grafo.prerequisitos(c))


def test_lacuna_sorteada_e_reproduzivel(grafo):
    a = [gerar_aluno(grafo, random.Random(SEMENTE))["lacuna"] for _ in range(3)]
    b = [gerar_aluno(grafo, random.Random(SEMENTE))["lacuna"] for _ in range(3)]
    assert a == b


def test_responder_segue_os_parametros_do_simulador():
    rng = random.Random(SEMENTE)
    n = 20_000
    dominio = {"a": 1, "b": 0}
    acertos_dominando = sum(responder(dominio, ["a"], rng, 0.10, 0.25) for _ in range(n)) / n
    acertos_sem_dominar = sum(responder(dominio, ["a", "b"], rng, 0.10, 0.25) for _ in range(n)) / n
    assert acertos_dominando == pytest.approx(0.90, abs=0.01)
    assert acertos_sem_dominar == pytest.approx(0.25, abs=0.01)


# --- Sessão simulada ---

@pytest.mark.parametrize("aleatoria", [False, True])
def test_sessao_respeita_minimo_e_maximo_de_questoes(grafo, espaco, itens, aleatoria):
    for lacuna in ("variavel", "escopo", "matriz"):
        rng = random.Random(SEMENTE)
        aluno = gerar_aluno(grafo, rng, lacuna=lacuna)
        sessao = simular_sessao(aluno["dominio"], itens, espaco, rng,
                                random.Random(SEMENTE) if aleatoria else None)
        assert MIN_QUESTOES <= len(sessao["respondidos"]) <= MAX_QUESTOES
        assert len(set(sessao["respondidos"])) == len(sessao["respondidos"])


@pytest.mark.parametrize("lacuna", ["variavel", "laco", "escopo", "matriz"])
def test_aluno_sem_ruido_e_diagnosticado_corretamente(grafo, espaco, itens, lacuna):
    """Sem deslize nem chute no aluno simulado, o motor acha a lacuna plantada."""
    aluno = gerar_aluno(grafo, random.Random(SEMENTE), lacuna=lacuna)
    sessao = simular_sessao(aluno["dominio"], itens, espaco, random.Random(SEMENTE),
                            deslize=0.0, chute=0.0)
    assert sessao["diagnostico"]["lacunas_raiz"][:1] == [lacuna]


def test_aluno_sem_lacuna_e_sem_ruido_nao_recebe_lacuna(grafo, espaco, itens):
    aluno = aluno_sem_lacuna(grafo)
    sessao = simular_sessao(aluno["dominio"], itens, espaco, random.Random(SEMENTE),
                            deslize=0.0, chute=0.0)
    assert sessao["diagnostico"]["lacunas_raiz"] == []


# --- Experimento ---

def test_experimento_e_reproduzivel(espaco, itens):
    cfg = CONFIGURACOES[0]
    rodar = lambda: rodar_configuracao(cfg, espaco, itens, alunos_por_conceito=1, alunos_sem_lacuna=2)
    assert rodar() == rodar()


def test_experimento_cobre_todos_os_conceitos_e_o_grupo_sem_lacuna(grafo, espaco, itens):
    linhas = rodar_configuracao(CONFIGURACOES[1], espaco, itens, alunos_por_conceito=2, alunos_sem_lacuna=3)
    assert len(linhas) == 2 * len(grafo.conceitos) + 3
    assert {l["lacuna_plantada"] for l in linhas} == set(grafo.conceitos) | {None}


def test_top1_implica_top2(espaco, itens):
    for l in rodar_configuracao(CONFIGURACOES[2], espaco, itens, alunos_por_conceito=1, alunos_sem_lacuna=0):
        assert not l["acerto_top1"] or l["acerto_top2"]


def _linha(lacuna, top1, top2, n, situacao, raizes=()):
    return {"lacuna_plantada": lacuna, "acerto_top1": top1, "acerto_top2": top2,
            "n_questoes": n, "situacao": situacao, "lacunas_raiz": list(raizes)}


def test_resumir_calcula_as_metricas():
    linhas = [
        _linha("a", True, True, 6, "lacunas", ["a"]),
        _linha("a", False, True, 10, "lacunas", ["x", "a"]),
        _linha("b", False, False, 14, "inconclusivo"),
        _linha("b", False, False, 10, "lacunas", ["x"]),
        _linha(None, True, True, 15, "inconclusivo"),
        _linha(None, False, False, 15, "lacunas", ["x"]),
        _linha(None, True, True, 15, "sem_lacunas"),
        _linha(None, True, True, 15, "sem_lacunas"),
    ]
    r = resumir(linhas)
    assert r == {"n": 4, "acerto_top1": 0.25, "acerto_top2": 0.5,
                 "media_questoes": 10.0, "taxa_inconclusivo": 0.25,
                 "n_sem_lacuna": 4, "taxa_lacuna_falsa": 0.25}
    por = resumir_por_conceito(linhas, ["a", "b", "c"])
    assert set(por) == {"a", "b"}
    assert por["a"]["acerto_top1"] == 0.5
    assert por["a"]["taxa_lacuna_falsa"] is None


def test_resumir_sem_alunos_com_lacuna():
    with pytest.raises(ValueError):
        resumir([])
    with pytest.raises(ValueError):
        resumir([_linha(None, True, True, 15, "sem_lacunas")])

