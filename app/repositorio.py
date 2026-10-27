"""Consultas SQL. É a única camada que fala com o banco."""

from __future__ import annotations

import json
import sqlite3

# --- Conteúdo (conceitos e itens) ---


def substituir_conteudo(con: sqlite3.Connection, conceitos: list[dict], itens: list[dict]) -> None:
    """Apaga e recarrega conceitos, pré-requisitos e itens. Não toca em alunos nem respostas."""
    with con:
        for tabela in ("item_conceito", "item", "prerequisito", "conceito"):
            con.execute(f"DELETE FROM {tabela}")
        con.executemany(
            "INSERT INTO conceito (id, nome, descricao) VALUES (?, ?, ?)",
            [(c["id"], c["nome"], c.get("descricao")) for c in conceitos],
        )
        con.executemany(
            "INSERT INTO prerequisito (conceito_id, prereq_id) VALUES (?, ?)",
            [(c["id"], p) for c in conceitos for p in c["prerequisitos"]],
        )
        con.executemany(
            "INSERT INTO item (id, enunciado, codigo, opcoes, correta, explicacao) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (i["id"], i["enunciado"], i["codigo"], json.dumps(i["opcoes"], ensure_ascii=False),
                 i["correta"], i["explicacao"])
                for i in itens
            ],
        )
        con.executemany(
            "INSERT INTO item_conceito (item_id, conceito_id) VALUES (?, ?)",
            [(i["id"], c) for i in itens for c in i["conceitos"]],
        )


def listar_conceitos(con: sqlite3.Connection) -> list[dict]:
    """Conceitos com a lista de pré-requisitos, na ordem em que foram cadastrados."""
    prereqs: dict[str, list[str]] = {}
    for linha in con.execute("SELECT conceito_id, prereq_id FROM prerequisito ORDER BY rowid"):
        prereqs.setdefault(linha["conceito_id"], []).append(linha["prereq_id"])
    return [
        {"id": l["id"], "nome": l["nome"], "descricao": l["descricao"], "prerequisitos": prereqs.get(l["id"], [])}
        for l in con.execute("SELECT id, nome, descricao FROM conceito ORDER BY rowid")
    ]


def listar_itens(con: sqlite3.Connection) -> list[dict]:
    """Itens completos (inclusive a resposta correta), na ordem em que foram cadastrados."""
    conceitos: dict[str, list[str]] = {}
    for linha in con.execute("SELECT item_id, conceito_id FROM item_conceito ORDER BY rowid"):
        conceitos.setdefault(linha["item_id"], []).append(linha["conceito_id"])
    return [
        {
            "id": l["id"], "enunciado": l["enunciado"], "codigo": l["codigo"],
            "opcoes": json.loads(l["opcoes"]), "correta": l["correta"],
            "explicacao": l["explicacao"], "conceitos": conceitos.get(l["id"], []),
        }
        for l in con.execute("SELECT * FROM item ORDER BY rowid")
    ]


# --- Alunos ---


def buscar_aluno_por_nome(con: sqlite3.Connection, nome: str) -> dict | None:
    """Aluno real (não simulado) com esse nome, sem diferenciar maiúsculas."""
    linha = con.execute(
        "SELECT * FROM aluno WHERE simulado = 0 AND lower(nome) = lower(?) ORDER BY id LIMIT 1", (nome,)
    ).fetchone()
    return dict(linha) if linha else None


def buscar_aluno(con: sqlite3.Connection, aluno_id: int) -> dict | None:
    linha = con.execute("SELECT * FROM aluno WHERE id = ?", (aluno_id,)).fetchone()
    return dict(linha) if linha else None


def criar_aluno(con: sqlite3.Connection, nome: str, simulado: bool = False,
                lacuna_plantada: str | None = None) -> int:
    with con:
        cur = con.execute(
            "INSERT INTO aluno (nome, simulado, lacuna_plantada) VALUES (?, ?, ?)",
            (nome, int(simulado), lacuna_plantada),
        )
    return cur.lastrowid


def listar_alunos(con: sqlite3.Connection) -> list[dict]:
    return [dict(l) for l in con.execute("SELECT * FROM aluno ORDER BY id")]


def apagar_alunos_simulados(con: sqlite3.Connection) -> int:
    """Remove alunos simulados com suas sessões e respostas. Devolve quantos alunos saíram."""
    with con:
        con.execute(
            "DELETE FROM resposta WHERE sessao_id IN "
            "(SELECT s.id FROM sessao s JOIN aluno a ON a.id = s.aluno_id WHERE a.simulado = 1)"
        )
        con.execute("DELETE FROM sessao WHERE aluno_id IN (SELECT id FROM aluno WHERE simulado = 1)")
        return con.execute("DELETE FROM aluno WHERE simulado = 1").rowcount


# --- Sessões e respostas ---


def criar_sessao(con: sqlite3.Connection, aluno_id: int, agora: str) -> int:
    with con:
        cur = con.execute("INSERT INTO sessao (aluno_id, iniciada_em) VALUES (?, ?)", (aluno_id, agora))
    return cur.lastrowid


def buscar_sessao(con: sqlite3.Connection, sessao_id: int) -> dict | None:
    linha = con.execute("SELECT * FROM sessao WHERE id = ?", (sessao_id,)).fetchone()
    return dict(linha) if linha else None


def encerrar_sessao(con: sqlite3.Connection, sessao_id: int, agora: str) -> None:
    with con:
        con.execute(
            "UPDATE sessao SET encerrada_em = ? WHERE id = ? AND encerrada_em IS NULL", (agora, sessao_id)
        )


def ultima_sessao_com_respostas(con: sqlite3.Connection, aluno_id: int) -> dict | None:
    """Sessão mais recente do aluno que tenha ao menos uma resposta."""
    linha = con.execute(
        "SELECT s.* FROM sessao s WHERE s.aluno_id = ? "
        "AND EXISTS (SELECT 1 FROM resposta r WHERE r.sessao_id = s.id) "
        "ORDER BY s.id DESC LIMIT 1",
        (aluno_id,),
    ).fetchone()
    return dict(linha) if linha else None


def listar_respostas(con: sqlite3.Connection, sessao_id: int) -> list[dict]:
    """Respostas da sessão em ordem."""
    return [
        dict(l) for l in con.execute(
            "SELECT * FROM resposta WHERE sessao_id = ? ORDER BY ordem", (sessao_id,)
        )
    ]


def inserir_resposta(con: sqlite3.Connection, sessao_id: int, item_id: str, opcao: int,
                     acertou: bool, ordem: int, agora: str) -> None:
    with con:
        con.execute(
            "INSERT INTO resposta (sessao_id, item_id, opcao, acertou, ordem, respondida_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sessao_id, item_id, opcao, int(acertou), ordem, agora),
        )
