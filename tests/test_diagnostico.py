"""Testes do critério de parada, do diagnóstico e da reprodução de sessões."""

import pytest

from app.config import GANHO_MINIMO, MAX_QUESTOES, MIN_QUESTOES
from app.motor.diagnostico import (
    classificar,
    classificar_conceitos,
    crenca_apos,
    deve_parar,
    diagnosticar,
    erros_por_conceito,
    escolher_proxima,
    lacunas_raiz,
    reproduzir,
)
from app.motor.modelo import crenca_inicial


def _estado(grafo, **valores: float) -> dict[str, float]:
    """Estado com todos os conceitos dominados (0.9), exceto os informados."""
    estado = {c: 0.9 for c in grafo.conceitos}
    estado.update(valores)
    return estado


# --- Classificação ---

@pytest.mark.parametrize("p, esperado", [
    (0.0, "lacuna"), (0.30, "lacuna"), (0.31, "incerto"),
    (0.5, "incerto"), (0.69, "incerto"), (0.70, "dominado"), (1.0, "dominado"),
])
def test_classificar_pelos_limiares(p, esperado):
    assert classificar(p) == esperado


# --- Critério de parada ---

def test_para_no_maximo_de_questoes():
    incerto = {"a": 0.5}
    assert deve_parar(incerto, MAX_QUESTOES, melhor_ganho=1.0)


def test_nao_para_antes_do_minimo_mesmo_sem_ganho_ou_tudo_classificado():
    assert not deve_parar({"a": 0.9}, MIN_QUESTOES - 1, melhor_ganho=0.0)


def test_para_quando_nao_ha_mais_ganho_relevante():
    assert deve_parar({"a": 0.5}, MIN_QUESTOES, melhor_ganho=GANHO_MINIMO / 2)


def test_para_quando_tudo_esta_classificado():
    assert deve_parar({"a": 0.9, "b": 0.1}, MIN_QUESTOES, melhor_ganho=0.5)


def test_continua_se_ha_incerteza_e_ganho():
    assert not deve_parar({"a": 0.9, "b": 0.5}, MIN_QUESTOES, melhor_ganho=0.5)


# --- Lacuna raiz ---

def test_raiz_e_escopo_nao_recursao(grafo):
    estado = _estado(grafo, escopo=0.1, recursao=0.05)
    assert lacunas_raiz(estado, grafo) == ["escopo"]


def test_raiz_considera_pre_requisitos_indiretos(grafo):
    # escopo está incerto, mas parametro (pré-requisito de escopo) tem lacuna:
    # a causa provável da lacuna em recursao está em parametro.
    estado = _estado(grafo, parametro=0.2, escopo=0.5, recursao=0.1)
    assert lacunas_raiz(estado, grafo) == ["parametro"]


def test_raizes_independentes_ordenadas_por_p(grafo):
    estado = _estado(grafo, escopo=0.25, laco_aninhado=0.1, matriz=0.05)
    assert lacunas_raiz(estado, grafo) == ["laco_aninhado", "escopo"]


def test_sem_lacunas_nao_ha_raiz(grafo):
    assert lacunas_raiz(_estado(grafo), grafo) == []


# --- Diagnóstico ---

def test_diagnostico_com_lacunas(grafo):
    estado = _estado(grafo, escopo=0.1, recursao=0.2)
    d = diagnosticar(estado, grafo)
    assert d["situacao"] == "lacunas"
    assert d["lacunas_raiz"] == ["escopo"]
    assert d["recomendacoes"] == [
        {"conceito": "escopo", "texto": "Revisar Escopo de variável", "destravar": ["recursao"]}
    ]
    assert d["classificacao"]["escopo"] == "lacuna"
    assert d["classificacao"]["variavel"] == "dominado"


def test_recomendacao_lista_so_descendentes_nao_dominados(grafo):
    estado = _estado(grafo, laco=0.1, vetor=0.2, matriz=0.5)
    d = diagnosticar(estado, grafo)
    assert d["lacunas_raiz"] == ["laco"]
    assert d["recomendacoes"][0]["destravar"] == ["vetor", "matriz"]


def test_diagnostico_sem_lacunas(grafo):
    assert diagnosticar(_estado(grafo), grafo)["situacao"] == "sem_lacunas"


def test_diagnostico_inconclusivo(grafo):
    d = diagnosticar(_estado(grafo, escopo=0.5), grafo)
    assert d["situacao"] == "inconclusivo"
    assert d["lacunas_raiz"] == []


def test_classificacao_em_ordem_topologica(grafo):
    d = diagnosticar(_estado(grafo), grafo)
    assert list(d["classificacao"]) == grafo.ordem_topologica()


# --- Confirmação da lacuna (dois erros) ---

def _respostas(*pares: tuple[list[str], bool]) -> list[tuple[dict, bool]]:
    return [({"id": f"t{i}", "conceitos": c}, acertou) for i, (c, acertou) in enumerate(pares)]


def test_erros_contam_o_conceito_do_item_e_seus_pre_requisitos(grafo):
    erros = erros_por_conceito(_respostas((["escopo"], False), (["escopo"], True)), grafo)
    assert {c for c, n in erros.items() if n} == {"escopo", "parametro", "funcao", "variavel"}
    assert erros["escopo"] == 1
    assert erros["recursao"] == 0


def test_um_erro_so_nao_confirma_a_lacuna(grafo):
    """Um erro isolado pode ser deslize: com p baixo, o conceito fica 'nao_confirmada'."""
    estado = _estado(grafo, escopo=0.1, recursao=0.05)
    erros = erros_por_conceito(_respostas((["escopo"], False)), grafo)
    d = diagnosticar(estado, grafo, erros)
    assert d["classificacao"]["escopo"] == "nao_confirmada"
    assert d["lacunas_raiz"] == []
    assert d["situacao"] == "inconclusivo"


def test_dois_erros_confirmam_a_lacuna(grafo):
    estado = _estado(grafo, escopo=0.1, recursao=0.05)
    erros = erros_por_conceito(_respostas((["escopo"], False), (["escopo", "parametro"], False)), grafo)
    d = diagnosticar(estado, grafo, erros)
    assert d["classificacao"]["escopo"] == "lacuna"
    assert d["lacunas_raiz"] == ["escopo"]


def test_p_baixo_sem_erro_nenhum_nao_e_lacuna(grafo):
    """p baixo que vem só da estimativa inicial (nenhum erro) não é lacuna."""
    estado = _estado(grafo, recursao=0.02, matriz=0.03)
    erros = erros_por_conceito(_respostas((["variavel"], True), (["laco"], True)), grafo)
    d = diagnosticar(estado, grafo, erros)
    assert d["classificacao"]["recursao"] == "nao_confirmada"
    assert d["classificacao"]["matriz"] == "nao_confirmada"
    assert d["lacunas_raiz"] == []


def test_lacuna_herdada_de_pre_requisito_confirmado(grafo):
    """Sem domínio de variável não há domínio de recursão, mesmo sem questão de recursão."""
    estado = {c: 0.02 for c in grafo.conceitos}
    erros = erros_por_conceito(_respostas((["variavel"], False), (["variavel"], False)), grafo)
    d = diagnosticar(estado, grafo, erros)
    assert d["classificacao"]["recursao"] == "lacuna"
    assert d["lacunas_raiz"] == ["variavel"]


def test_lacuna_nao_confirmada_nao_vira_raiz(grafo):
    estado = _estado(grafo, escopo=0.1, matriz=0.03)
    erros = erros_por_conceito(_respostas((["escopo"], False), (["escopo"], False), (["matriz"], False)), grafo)
    assert lacunas_raiz(estado, grafo, erros) == ["escopo"]


def test_lacuna_nao_confirmada_mantem_a_sessao_aberta(grafo):
    estado = _estado(grafo, escopo=0.1)
    um_erro = classificar_conceitos(estado, grafo, erros_por_conceito(_respostas((["escopo"], False)), grafo))
    assert not deve_parar(estado, MIN_QUESTOES, melhor_ganho=0.5, classificacao=um_erro)
    dois = _respostas((["escopo"], False), (["escopo"], False))
    confirmada = classificar_conceitos(estado, grafo, erros_por_conceito(dois, grafo))
    assert deve_parar(estado, MIN_QUESTOES, melhor_ganho=0.5, classificacao=confirmada)


# --- Reprodução ---

ITENS = [
    {"id": "q1", "conceitos": ["recursao", "escopo", "retorno"]},
    {"id": "q2", "conceitos": ["escopo"]},
    {"id": "q3", "conceitos": ["retorno"]},
    {"id": "q4", "conceitos": ["tipos"]},
]
RESPOSTAS = [("q1", False), ("q2", False), ("q3", True)]


def test_reproduzir_sem_respostas_devolve_priori(espaco):
    crenca, trilha = reproduzir([], ITENS, espaco)
    assert crenca.pesos == crenca_inicial(espaco).pesos
    assert trilha == []


def test_reproduzir_e_deterministico(espaco):
    c1, t1 = reproduzir(RESPOSTAS, ITENS, espaco)
    c2, t2 = reproduzir(RESPOSTAS, ITENS, espaco)
    assert c1.pesos == c2.pesos
    assert t1 == t2


def test_crenca_apos_da_o_mesmo_que_reproduzir(espaco):
    assert crenca_apos(RESPOSTAS, ITENS, espaco).pesos == reproduzir(RESPOSTAS, ITENS, espaco)[0].pesos


def test_reproduzir_monta_a_trilha_de_raciocinio(espaco):
    crenca, trilha = reproduzir(RESPOSTAS, ITENS, espaco)
    assert [t["ordem"] for t in trilha] == [1, 2, 3]
    assert [t["item_id"] for t in trilha] == ["q1", "q2", "q3"]

    primeiro = trilha[0]
    assert primeiro["acertou"] is False
    do_item = [m for m in primeiro["mudancas"] if m["no_item"]]
    assert [m["conceito"] for m in do_item] == ["recursao", "escopo", "retorno"]
    assert all(m["depois"] < m["antes"] for m in do_item)
    assert "entre 4 itens" in primeiro["motivo_escolha"]
    assert trilha[1]["conceito_em_teste"] == "escopo"
    # Depois do erro no item composto, o motor volta a escopo para confirmar a lacuna.
    assert trilha[1]["motivo_escolha"].startswith("confirmar a lacuna em Escopo de variável (1 erro")
    assert "entre 1 item que testa o conceito" in trilha[1]["motivo_escolha"]

    escopo_depois_1 = next(m["depois"] for m in primeiro["mudancas"] if m["conceito"] == "escopo")
    escopo_antes_2 = next(m["antes"] for m in trilha[1]["mudancas"] if m["conceito"] == "escopo")
    assert escopo_antes_2 == pytest.approx(escopo_depois_1, abs=1e-4)

    estado = crenca.estado
    assert estado["escopo"] < estado["retorno"]


def test_trilha_mostra_o_efeito_pelo_grafo(espaco):
    """Errar escopo também derruba recursao, que depende dele; isso aparece na trilha."""
    _, trilha = reproduzir([("q2", False)], ITENS, espaco)
    pelo_grafo = {m["conceito"]: m for m in trilha[0]["mudancas"] if not m["no_item"]}
    assert "recursao" in pelo_grafo
    assert pelo_grafo["recursao"]["depois"] < pelo_grafo["recursao"]["antes"]


def test_trilha_explica_cada_escolha_quando_segue_o_motor(espaco, itens):
    """Seguindo a política adaptativa, cada passo é 'maior ganho' ou 'confirmar a lacuna'."""
    por_id = {i["id"]: i for i in itens}
    respostas: list[tuple[str, bool]] = []
    confirmacoes = []
    for acertou in (False, False, True, False, True, True):
        crenca = crenca_apos(respostas, itens, espaco)
        erros = erros_por_conceito([(por_id[i], a) for i, a in respostas], espaco.grafo)
        item, _, confirmando = escolher_proxima(crenca, itens, {i for i, _ in respostas}, erros)
        confirmacoes.append(confirmando)
        respostas.append((item["id"], acertou))
    _, trilha = reproduzir(respostas, itens, espaco)
    for passo, confirmando in zip(trilha, confirmacoes):
        esperado = "confirmar a lacuna" if confirmando else "maior ganho esperado"
        assert passo["motivo_escolha"].startswith(esperado)
    assert any(confirmacoes), "a sequência de erros deveria provocar ao menos uma confirmação"


def test_escolher_proxima_volta_ao_conceito_com_um_erro(espaco, itens):
    por_id = {i["id"]: i for i in itens}
    respostas = [("q39", False)]   # item puro de escopo, errado
    crenca = crenca_apos(respostas, itens, espaco)
    erros = erros_por_conceito([(por_id["q39"], False)], espaco.grafo)
    item, _, confirmando = escolher_proxima(crenca, itens, {"q39"}, erros)
    assert confirmando == "escopo"
    assert "escopo" in item["conceitos"]


def test_reproduzir_explica_quando_o_item_nao_era_o_melhor(espaco, itens):
    _, trilha = reproduzir([("q45", True)], itens, espaco)
    assert "o maior disponível era" in trilha[0]["motivo_escolha"]


def test_reproduzir_rejeita_item_repetido_ou_desconhecido(espaco):
    with pytest.raises(ValueError, match="duas vezes"):
        reproduzir([("q1", True), ("q1", False)], ITENS, espaco)
    with pytest.raises(ValueError, match="desconhecido"):
        reproduzir([("q99", True)], ITENS, espaco)

