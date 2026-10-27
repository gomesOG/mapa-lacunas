"""Roda o experimento de validação (configurações A, B e C) e gera a métrica do slide.

Uso: python scripts/validar_motor.py
Saídas: tabela no terminal, resultados/validacao.csv e resultados/resumo.md.
"""

import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.motor.grafo import carregar_grafo  # noqa: E402
from app.motor.modelo import montar_espaco  # noqa: E402
from app.simulacao.experimento import (  # noqa: E402
    ALUNOS_POR_CONCEITO,
    CONFIGURACOES,
    resumir,
    resumir_por_conceito,
    rodar_configuracao,
)

COLUNAS_CSV = [
    "configuracao", "aluno", "lacuna_plantada", "lacunas_raiz",
    "situacao", "n_questoes", "acerto_top1", "acerto_top2",
]


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _descrever(cfg: dict) -> str:
    return f"{cfg['selecao']}, s = {cfg['deslize']:.2f}, g = {cfg['chute']:.2f}"


def imprimir_tabela(resumos: dict[str, dict]) -> None:
    """Mostra as métricas de cada configuração no terminal."""
    cabecalho = (
        f"{'Config':<7}{'Seleção / ruído do simulador':<38}{'Top-1':>8}{'Top-2':>8}"
        f"{'Questões':>10}{'Inconcl.':>10}{'Lacuna falsa*':>15}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for cfg in CONFIGURACOES:
        r = resumos[cfg["nome"]]
        print(
            f"{cfg['nome']:<7}{_descrever(cfg):<38}{_pct(r['acerto_top1']):>8}"
            f"{_pct(r['acerto_top2']):>8}{r['media_questoes']:>10.1f}{_pct(r['taxa_inconclusivo']):>10}"
            f"{_pct(r['taxa_lacuna_falsa']):>15}"
        )
    n_sem = resumos[CONFIGURACOES[0]["nome"]]["n_sem_lacuna"]
    print(f"* entre {n_sem} alunos sem lacuna: quantos saíram com alguma lacuna raiz (menor é melhor)")


def gravar_csv(caminho: Path, linhas: list[dict]) -> None:
    """Uma linha por aluno simulado."""
    with caminho.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_CSV)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({**linha, "lacunas_raiz": ";".join(linha["lacunas_raiz"])})


def gravar_resumo(caminho: Path, resumos: dict, por_conceito: dict, grafo) -> None:
    """Resumo em Markdown, pronto para colar no slide."""
    a, b, c = (resumos[n] for n in ("A", "B", "C"))
    partes = [
        "# Validação do motor com alunos simulados",
        "",
        f"Por configuração: {a['n']} alunos com uma lacuna plantada ({ALUNOS_POR_CONCEITO} por conceito, "
        f"{len(grafo.conceitos)} conceitos), em que a lacuna e todos os conceitos que dependem dela "
        f"ficam sem domínio, e mais {a['n_sem_lacuna']} alunos que dominam tudo. "
        f"Semente fixa = {config.SEMENTE}.",
        "",
        "O motor usa o modelo DINA sobre os estados de conhecimento viáveis do grafo de "
        "pré-requisitos, escolhe cada questão pelo maior ganho de informação esperado (voltando "
        f"ao conceito para confirmar uma lacuna) e só declara lacuna após {config.ERROS_PARA_LACUNA} "
        "erros em questões que exigem o conceito.",
        "",
        "| Config | Seleção | Ruído do simulador | Acerto top-1 | Acerto top-2 | Média de questões "
        "| Inconclusivo | Lacuna falsa (sem lacuna) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cfg in CONFIGURACOES:
        r = resumos[cfg["nome"]]
        partes.append(
            f"| {cfg['nome']} | {cfg['selecao']} | s = {cfg['deslize']:.2f}; g = {cfg['chute']:.2f} | "
            f"{_pct(r['acerto_top1'])} | {_pct(r['acerto_top2'])} | {r['media_questoes']:.1f} | "
            f"{_pct(r['taxa_inconclusivo'])} | {_pct(r['taxa_lacuna_falsa'])} |"
        )
    partes += [
        "",
        "## Leitura",
        "",
        f"- **Adaptativa x aleatória (A x B):** top-1 de {_pct(a['acerto_top1'])} contra "
        f"{_pct(b['acerto_top1'])}, com {a['media_questoes']:.1f} contra {b['media_questoes']:.1f} questões em média.",
        f"- **Robustez (C):** com o aluno simulado mais ruidoso que o modelo do motor, o top-1 fica em "
        f"{_pct(c['acerto_top1'])} (top-2: {_pct(c['acerto_top2'])}).",
        f"- **Lacunas falsas (A):** {_pct(a['taxa_lacuna_falsa'])} dos alunos que dominam tudo saíram com "
        "alguma lacuna raiz apontada.",
        "",
        "## Acerto top-1 por lacuna plantada",
        "",
        "| Conceito | A | B | C |",
        "|---|---|---|---|",
    ]
    for conceito in grafo.ordem_topologica():
        valores = " | ".join(_pct(por_conceito[n][conceito]["acerto_top1"]) for n in ("A", "B", "C"))
        partes.append(f"| {grafo.nome(conceito)} | {valores} |")
    caminho.write_text("\n".join(partes) + "\n", encoding="utf-8")


def main() -> None:
    grafo = carregar_grafo(json.loads(config.ARQUIVO_CONCEITOS.read_text(encoding="utf-8")))
    itens = json.loads(config.ARQUIVO_ITENS.read_text(encoding="utf-8"))
    espaco = montar_espaco(grafo)
    print(f"{len(espaco.estados)} estados de conhecimento viáveis no grafo\n")

    todas: list[dict] = []
    resumos: dict[str, dict] = {}
    por_conceito: dict[str, dict] = {}
    for cfg in CONFIGURACOES:
        inicio = time.perf_counter()
        linhas = rodar_configuracao(cfg, espaco, itens)
        resumos[cfg["nome"]] = resumir(linhas)
        por_conceito[cfg["nome"]] = resumir_por_conceito(linhas, grafo.conceitos)
        todas.extend(linhas)
        print(f"Configuração {cfg['nome']}: {len(linhas)} alunos em {time.perf_counter() - inicio:.1f} s")

    print()
    imprimir_tabela(resumos)

    config.PASTA_RESULTADOS.mkdir(exist_ok=True)
    gravar_csv(config.PASTA_RESULTADOS / "validacao.csv", todas)
    gravar_resumo(config.PASTA_RESULTADOS / "resumo.md", resumos, por_conceito, grafo)
    print(f"\nArquivos gerados em {config.PASTA_RESULTADOS}: validacao.csv, resumo.md")


if __name__ == "__main__":
    main()
