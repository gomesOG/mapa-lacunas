"""App FastAPI: rotas da API e arquivos estáticos.

Rodar: uvicorn app.main:app --reload  (documentação interativa em /docs)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config
from app.servico import Conflito, DadoInvalido, NaoEncontrado, Servico

servico = Servico(config.CAMINHO_BANCO)


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    servico.conteudo  # falha logo na partida, com mensagem clara, se o banco não existir
    yield


app = FastAPI(
    title="Mapa de Lacunas Conceituais",
    description="Diagnóstico de lacunas em Algoritmos e Programação I (modelo DINA + grafo de pré-requisitos).",
    lifespan=ciclo_de_vida,
)


class NovaSessao(BaseModel):
    nome: str = Field(min_length=1, examples=["Ana"])


class NovaResposta(BaseModel):
    item_id: str = Field(examples=["q39"])
    opcao: int = Field(ge=0, le=3, description="Índice da opção escolhida (0 a 3)")


@app.exception_handler(NaoEncontrado)
async def _nao_encontrado(_: Request, erro: NaoEncontrado) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(erro)})


@app.exception_handler(Conflito)
async def _conflito(_: Request, erro: Conflito) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(erro)})


@app.exception_handler(DadoInvalido)
async def _dado_invalido(_: Request, erro: DadoInvalido) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(erro)})


@app.get("/api/conceitos", tags=["conteúdo"])
def listar_conceitos() -> list[dict]:
    """Conceitos com pré-requisitos, em ordem topológica (da base para o topo)."""
    return servico.listar_conceitos()


@app.post("/api/sessoes", tags=["aluno"])
def criar_sessao(dados: NovaSessao) -> dict:
    """Inicia uma sessão. Cria o aluno se o nome ainda não existir."""
    return servico.iniciar_sessao(dados.nome)


@app.get("/api/sessoes/{sessao_id}/proximo", tags=["aluno"])
def proximo_item(sessao_id: int) -> dict:
    """Próxima questão escolhida pelo motor (sem a resposta correta), ou {"fim": true}."""
    return servico.proximo(sessao_id)


@app.post("/api/sessoes/{sessao_id}/respostas", tags=["aluno"])
def responder(sessao_id: int, dados: NovaResposta) -> dict:
    """Registra a resposta. Responder de novo o mesmo item retorna 409."""
    return servico.responder(sessao_id, dados.item_id, dados.opcao)


@app.get("/api/sessoes/{sessao_id}/diagnostico", tags=["aluno"])
def diagnostico(sessao_id: int) -> dict:
    """Diagnóstico, estado por conceito e trilha de raciocínio do motor."""
    return servico.diagnostico(sessao_id)


@app.get("/api/turma/mapa", tags=["professor"])
def mapa_turma() -> dict:
    """Estado da última sessão de cada aluno (mapa de calor) e conceitos mais críticos."""
    return servico.mapa_turma()


@app.get("/api/turma/risco", tags=["professor"])
def risco_turma() -> list[dict]:
    """Alunos com lacuna raiz, ordenados pela quantidade de lacunas."""
    return servico.risco_turma()


@app.get("/api/alunos/{aluno_id}", tags=["professor"])
def detalhe_aluno(aluno_id: int) -> dict:
    """Dados do aluno e diagnóstico da última sessão."""
    return servico.detalhe_aluno(aluno_id)


# Montado por último para não encobrir as rotas /api. Serve index.html em "/".
app.mount("/", StaticFiles(directory=config.PASTA_STATIC, html=True), name="static")
