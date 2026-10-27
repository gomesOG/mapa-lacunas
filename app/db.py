"""Conexão SQLite e criação do schema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import CAMINHO_BANCO

SCHEMA = """
CREATE TABLE IF NOT EXISTS conceito (id TEXT PRIMARY KEY, nome TEXT NOT NULL, descricao TEXT);
CREATE TABLE IF NOT EXISTS prerequisito (conceito_id TEXT, prereq_id TEXT, PRIMARY KEY (conceito_id, prereq_id));
CREATE TABLE IF NOT EXISTS item (id TEXT PRIMARY KEY, enunciado TEXT, codigo TEXT, opcoes TEXT, correta INTEGER, explicacao TEXT);
CREATE TABLE IF NOT EXISTS item_conceito (item_id TEXT, conceito_id TEXT, PRIMARY KEY (item_id, conceito_id));
CREATE TABLE IF NOT EXISTS aluno (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
                                  simulado INTEGER DEFAULT 0, lacuna_plantada TEXT);
CREATE TABLE IF NOT EXISTS sessao (id INTEGER PRIMARY KEY AUTOINCREMENT, aluno_id INTEGER,
                                   iniciada_em TEXT, encerrada_em TEXT);
CREATE TABLE IF NOT EXISTS resposta (id INTEGER PRIMARY KEY AUTOINCREMENT, sessao_id INTEGER, item_id TEXT,
                                     opcao INTEGER, acertou INTEGER, ordem INTEGER, respondida_em TEXT);
"""


def conectar(caminho: Path | str = CAMINHO_BANCO) -> sqlite3.Connection:
    """Abre uma conexão com linhas acessíveis por nome (row['coluna'])."""
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    return con


def criar_schema(con: sqlite3.Connection) -> None:
    """Cria as tabelas que ainda não existem."""
    con.executescript(SCHEMA)
    con.commit()
