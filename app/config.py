"""Constantes do modelo e caminhos do projeto (único lugar onde ficam)."""

from pathlib import Path

# --- Caminhos ---
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"
ARQUIVO_CONCEITOS = PASTA_DADOS / "conceitos.json"
ARQUIVO_ITENS = PASTA_DADOS / "itens.json"
CAMINHO_BANCO = RAIZ / "mapa.db"
PASTA_STATIC = RAIZ / "static"
PASTA_RESULTADOS = RAIZ / "resultados"

# --- Modelo DINA ---
DESLIZE = 0.10          # s: chance de errar mesmo dominando tudo (slip)
CHUTE = 0.25            # g: chance de acertar sem dominar (4 opções)
PRIORI = 0.60           # chance inicial de dominar um conceito, dado que domina os pré-requisitos

# --- Classificação ---
LIMIAR_DOMINIO = 0.70   # p >= 0.70 -> dominado
LIMIAR_LACUNA = 0.30    # p <= 0.30 -> lacuna
ERROS_PARA_LACUNA = 2   # lacuna só é declarada após este número de erros em questões que exigem o conceito

# --- Sessão ---
MIN_QUESTOES = 6
MAX_QUESTOES = 15
GANHO_MINIMO = 0.01     # para de perguntar se nenhuma questão traz ganho maior que isto

# --- Reprodutibilidade ---
SEMENTE = 42
