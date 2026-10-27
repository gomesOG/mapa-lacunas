"""Testes da camada de serviço com um banco SQLite temporário."""

import pytest

from app import repositorio
from app.config import MAX_QUESTOES, MIN_QUESTOES
from app.db import conectar, criar_schema
from app.servico import Conflito, DadoInvalido, NaoEncontrado, Servico


@pytest.fixture
def servico(tmp_path, conceitos, itens) -> Servico:
    caminho = tmp_path / "teste.db"
    con = conectar(caminho)
    criar_schema(con)
    repositorio.substituir_conteudo(con, conceitos, itens)
    con.close()
    return Servico(caminho)


def _sessao_completa(servico: Servico, nome: str, sem_dominio: set[str]) -> int:
    """Faz uma sessão inteira: acerta quando domina todos os conceitos do item."""
    sessao_id = servico.iniciar_sessao(nome)["sessao_id"]
    por_id = servico.conteudo.itens_por_id
    while not (prox := servico.proximo(sessao_id))["fim"]:
        item = por_id[prox["item"]["id"]]
        domina = not (set(item["conceitos"]) & sem_dominio)
        opcao = item["correta"] if domina else (item["correta"] + 1) % 4
        servico.responder(sessao_id, item["id"], opcao)
    return sessao_id


# --- Conteúdo ---

def test_conceitos_em_ordem_topologica(servico, grafo):
    assert [c["id"] for c in servico.listar_conceitos()] == grafo.ordem_topologica()


def test_banco_inexistente_da_erro_claro(tmp_path):
    with pytest.raises(RuntimeError, match="criar_banco"):
        Servico(tmp_path / "nao_existe.db").listar_conceitos()


# --- Sessão ---

def test_iniciar_sessao_reaproveita_aluno_pelo_nome(servico):
    a = servico.iniciar_sessao("Ana Souza")
    b = servico.iniciar_sessao("  ana   souza ")
    assert a["aluno_id"] == b["aluno_id"]
    assert a["sessao_id"] != b["sessao_id"]


def test_nome_vazio_e_recusado(servico):
    with pytest.raises(DadoInvalido):
        servico.iniciar_sessao("   ")


def test_proximo_nao_revela_a_resposta(servico):
    sessao_id = servico.iniciar_sessao("Ana")["sessao_id"]
    prox = servico.proximo(sessao_id)
    assert prox["fim"] is False
    assert prox["ordem"] == 1
    assert "correta" not in prox["item"]
    assert "explicacao" not in prox["item"]
    assert prox["conceito_em_teste"]["id"] in prox["item"]["conceitos"]
    assert prox["ganho"] > 0


def test_responder_corrige_e_devolve_estado(servico):
    sessao_id = servico.iniciar_sessao("Ana")["sessao_id"]
    item = servico.proximo(sessao_id)["item"]
    correta = servico.conteudo.itens_por_id[item["id"]]["correta"]
    r = servico.responder(sessao_id, item["id"], correta)
    assert r["acertou"] is True
    assert r["correta"] == correta
    assert r["explicacao"]
    assert set(r["estado"]) == {c["id"] for c in servico.listar_conceitos()}


def test_responder_duas_vezes_o_mesmo_item_e_conflito(servico):
    sessao_id = servico.iniciar_sessao("Ana")["sessao_id"]
    item_id = servico.proximo(sessao_id)["item"]["id"]
    servico.responder(sessao_id, item_id, 0)
    with pytest.raises(Conflito):
        servico.responder(sessao_id, item_id, 1)


def test_erros_de_entrada(servico):
    sessao_id = servico.iniciar_sessao("Ana")["sessao_id"]
    with pytest.raises(NaoEncontrado):
        servico.responder(sessao_id, "q999", 0)
    with pytest.raises(DadoInvalido):
        servico.responder(sessao_id, "q01", 7)
    with pytest.raises(NaoEncontrado):
        servico.proximo(9999)
    with pytest.raises(NaoEncontrado):
        servico.diagnostico(9999)


def test_sessao_inteira_de_ponta_a_ponta(servico):
    sessao_id = _sessao_completa(servico, "Ana", sem_dominio={"escopo", "recursao"})
    d = servico.diagnostico(sessao_id)
    n = d["sessao"]["n_respondidas"]
    assert MIN_QUESTOES <= n <= MAX_QUESTOES
    assert d["sessao"]["encerrada"] is True
    assert len(d["trilha"]) == n
    assert d["aluno"]["nome"] == "Ana"
    assert d["diagnostico"]["situacao"] in {"lacunas", "sem_lacunas", "inconclusivo"}
    assert all("conceitos_item" in passo and "opcao" in passo for passo in d["trilha"])
    assert servico.proximo(sessao_id)["fim"] is True
    with pytest.raises(Conflito):
        servico.responder(sessao_id, "q01", 0)


def test_diagnostico_e_reproduzivel(servico):
    sessao_id = _sessao_completa(servico, "Bruno", sem_dominio={"laco_aninhado", "matriz"})
    assert servico.diagnostico(sessao_id) == servico.diagnostico(sessao_id)


def test_aluno_sem_lacunas_reais_sai_bem_diagnosticado(servico):
    sessao_id = _sessao_completa(servico, "Carla", sem_dominio={"recursao"})
    d = servico.diagnostico(sessao_id)["diagnostico"]
    assert d["classificacao"]["variavel"] == "dominado"


# --- Turma ---

def test_mapa_e_risco_da_turma(servico):
    _sessao_completa(servico, "Ana", sem_dominio={"escopo", "recursao"})
    _sessao_completa(servico, "Bruno", sem_dominio={"laco_aninhado", "matriz"})
    servico.iniciar_sessao("Sem respostas")

    mapa = servico.mapa_turma()
    assert [a["nome"] for a in mapa["alunos"]] == ["Ana", "Bruno"]
    assert len(mapa["criticos"]) == len(mapa["conceitos"]) == 15
    percentuais = [c["percentual"] for c in mapa["criticos"]]
    assert percentuais == sorted(percentuais, reverse=True)
    assert mapa["limiares"] == {"dominio": 0.70, "lacuna": 0.30}

    risco = servico.risco_turma()
    assert all(a["lacunas_raiz"] for a in risco)
    n = [a["n_lacunas"] for a in risco]
    assert n == sorted(n, reverse=True)


def test_mapa_usa_a_ultima_sessao_do_aluno(servico):
    _sessao_completa(servico, "Ana", sem_dominio={"variavel"})
    ultima = _sessao_completa(servico, "Ana", sem_dominio=set())
    aluno = servico.mapa_turma()["alunos"][0]
    assert aluno["sessao_id"] == ultima


def test_detalhe_do_aluno(servico):
    sessao_id = _sessao_completa(servico, "Ana", sem_dominio={"escopo"})
    aluno_id = servico.mapa_turma()["alunos"][0]["id"]
    detalhe = servico.detalhe_aluno(aluno_id)
    assert detalhe["aluno"]["nome"] == "Ana"
    assert detalhe["ultima_sessao"]["sessao"]["id"] == sessao_id

    novo = servico.iniciar_sessao("Novato")["aluno_id"]
    assert servico.detalhe_aluno(novo)["ultima_sessao"] is None
    with pytest.raises(NaoEncontrado):
        servico.detalhe_aluno(9999)
