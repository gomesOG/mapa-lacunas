"""Testes do grafo de pré-requisitos."""

import pytest

from app.motor.grafo import carregar_grafo


def _c(cid: str, *prereqs: str) -> dict:
    return {"id": cid, "nome": cid.upper(), "prerequisitos": list(prereqs)}


# --- Carga válida ---

def test_carrega_os_15_conceitos(grafo):
    assert len(grafo.conceitos) == 15
    assert grafo.nome("escopo") == "Escopo de variável"


def test_prerequisitos_diretos(grafo):
    assert grafo.prerequisitos("variavel") == []
    assert grafo.prerequisitos("busca_vetor") == ["vetor", "condicional"]
    assert set(grafo.prerequisitos("recursao")) == {"retorno", "escopo", "condicional"}


def test_dependentes_diretos(grafo):
    assert set(grafo.dependentes("laco")) == {"laco_aninhado", "vetor"}
    assert grafo.dependentes("recursao") == []


def test_conceito_desconhecido_lanca_keyerror(grafo):
    with pytest.raises(KeyError, match="desconhecido"):
        grafo.prerequisitos("ponteiro")


# --- Carga inválida ---

def test_prerequisito_inexistente():
    with pytest.raises(ValueError, match="inexistente: 'fantasma'"):
        carregar_grafo([_c("a"), _c("b", "fantasma")])


def test_ciclo_simples():
    with pytest.raises(ValueError, match="Ciclo"):
        carregar_grafo([_c("a", "c"), _c("b", "a"), _c("c", "b")])


def test_ciclo_mostra_os_conceitos_envolvidos():
    with pytest.raises(ValueError) as erro:
        carregar_grafo([_c("raiz"), _c("a", "raiz", "b"), _c("b", "a")])
    mensagem = str(erro.value)
    assert mensagem.endswith("a -> b -> a")
    assert "raiz" not in mensagem


def test_autorreferencia():
    with pytest.raises(ValueError, match="si mesmo"):
        carregar_grafo([_c("a", "a")])


def test_id_repetido():
    with pytest.raises(ValueError, match="repetido"):
        carregar_grafo([_c("a"), _c("a")])


# --- Ancestrais e descendentes ---

def test_ancestrais_de_recursao(grafo):
    assert set(grafo.ancestrais("recursao")) == {
        "retorno", "escopo", "parametro", "funcao",
        "condicional", "operadores", "variavel",
    }


def test_ancestrais_da_base_vazio(grafo):
    assert grafo.ancestrais("variavel") == []


def test_ancestrais_de_matriz(grafo):
    assert set(grafo.ancestrais("matriz")) == {
        "vetor", "laco_aninhado", "laco", "condicional", "operadores", "variavel",
    }


def test_descendentes_de_escopo(grafo):
    assert grafo.descendentes("escopo") == ["recursao"]


def test_descendentes_de_laco(grafo):
    assert set(grafo.descendentes("laco")) == {"laco_aninhado", "vetor", "busca_vetor", "matriz"}


def test_descendentes_de_variavel_sao_todos_os_outros(grafo):
    assert set(grafo.descendentes("variavel")) == set(grafo.conceitos) - {"variavel"}


def test_descendentes_do_topo_vazio(grafo):
    assert grafo.descendentes("recursao") == []
    assert grafo.descendentes("matriz") == []


# --- Ordem topológica ---

def test_ordem_topologica_respeita_prerequisitos(grafo):
    ordem = grafo.ordem_topologica()
    posicao = {c: i for i, c in enumerate(ordem)}
    assert sorted(ordem) == sorted(grafo.conceitos)
    for c in ordem:
        for p in grafo.prerequisitos(c):
            assert posicao[p] < posicao[c], f"{p} deveria vir antes de {c}"


def test_ordem_topologica_comeca_pela_base(grafo):
    assert grafo.ordem_topologica()[0] == "variavel"


def test_ordem_topologica_e_deterministica(conceitos):
    assert carregar_grafo(conceitos).ordem_topologica() == carregar_grafo(conceitos).ordem_topologica()


def test_ordem_topologica_independe_da_ordem_de_entrada():
    grafo = carregar_grafo([_c("c", "b"), _c("b", "a"), _c("a")])
    assert grafo.ordem_topologica() == ["a", "b", "c"]


def test_ancestrais_e_descendentes_em_ordem_topologica(grafo):
    ordem = grafo.ordem_topologica()
    for lista in (grafo.ancestrais("recursao"), grafo.descendentes("variavel")):
        assert lista == sorted(lista, key=ordem.index)
