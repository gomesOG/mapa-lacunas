"""Cria 30 alunos simulados com sessões completas, para o mapa de calor da apresentação.

Uso: python scripts/popular_turma.py   (rode antes: python scripts/criar_banco.py)

- É idempotente: apaga e recria apenas os alunos simulados (alunos reais ficam).
- As sessões passam pelo mesmo serviço usado pela API: o motor escolhe cada questão
  e o aluno simulado responde pelo modelo DINA.
- Ana (lacuna em escopo) e Bruno (lacuna em laço aninhado) são os exemplos do slide 5.
  Eles respondem de forma consistente com a lacuna, sem chute nem deslize, para a
  história do slide ser reproduzível. Os demais usam o ruído do modelo (s = 0,10; g = 0,25).
- Parte da turma tem lacuna concentrada em laço aninhado e em escopo; alguns alunos não
  têm lacuna nenhuma.
"""

import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, repositorio  # noqa: E402
from app.db import conectar  # noqa: E402
from app.servico import Servico  # noqa: E402
from app.simulacao.gerador import aluno_sem_lacuna, gerar_aluno, responder  # noqa: E402

OUTROS_NOMES = [
    "Carla", "Diego", "Eduarda", "Felipe", "Gabriela", "Heitor", "Isabela", "João",
    "Larissa", "Mateus", "Natália", "Otávio", "Paula", "Rafael", "Sofia", "Tiago",
    "Valentina", "Vinícius", "Yasmin", "Lucas", "Beatriz", "Caio", "Débora", "Enzo",
    "Fernanda", "Gustavo", "Helena", "Igor",
]
LACUNAS_CONCENTRADAS = {"escopo": 7, "laco_aninhado": 7}
SEM_LACUNA = 4


def plano_da_turma(conceitos: list[str], rng: random.Random) -> list[dict]:
    """Quem é cada aluno simulado, qual a lacuna plantada e se responde com ruído."""
    lacunas: list[str | None] = []
    for conceito, quantidade in LACUNAS_CONCENTRADAS.items():
        lacunas += [conceito] * quantidade
    lacunas += [None] * SEM_LACUNA
    outros = [c for c in conceitos if c not in LACUNAS_CONCENTRADAS]
    lacunas += [rng.choice(outros) for _ in range(len(OUTROS_NOMES) - len(lacunas))]
    rng.shuffle(lacunas)

    plano = [
        {"nome": "Ana", "lacuna": "escopo", "com_ruido": False},
        {"nome": "Bruno", "lacuna": "laco_aninhado", "com_ruido": False},
    ]
    plano += [{"nome": n, "lacuna": l, "com_ruido": True} for n, l in zip(OUTROS_NOMES, lacunas)]
    return plano


def simular(servico: Servico, sessao_id: int, dominio: dict[str, int], rng: random.Random,
            com_ruido: bool) -> int:
    """Responde a sessão inteira pelo serviço. Devolve quantas questões foram respondidas."""
    deslize, chute = (config.DESLIZE, config.CHUTE) if com_ruido else (0.0, 0.0)
    itens = servico.conteudo.itens_por_id
    n = 0
    while not (prox := servico.proximo(sessao_id))["fim"]:
        item = itens[prox["item"]["id"]]
        acertou = responder(dominio, item["conceitos"], rng, deslize, chute)
        erradas = [i for i in range(len(item["opcoes"])) if i != item["correta"]]
        opcao = item["correta"] if acertou else rng.choice(erradas)
        servico.responder(sessao_id, item["id"], opcao)
        n += 1
    return n


def main() -> None:
    if not config.CAMINHO_BANCO.exists():
        sys.exit("Banco não encontrado. Rode antes: python scripts/criar_banco.py")

    servico = Servico(config.CAMINHO_BANCO)
    grafo = servico.conteudo.grafo
    rng = random.Random(config.SEMENTE)

    con = conectar(config.CAMINHO_BANCO)
    try:
        removidos = repositorio.apagar_alunos_simulados(con)
        print(f"{removidos} alunos simulados anteriores removidos\n")
        print(f"{'Aluno':<12}{'Lacuna plantada':<22}{'Questões':>9}   Diagnóstico (lacunas raiz)")
        acertos = 0
        for aluno in plano_da_turma(grafo.conceitos, rng):
            lacuna = aluno["lacuna"]
            simulado = aluno_sem_lacuna(grafo) if lacuna is None else gerar_aluno(grafo, rng, lacuna=lacuna)
            dominio = simulado["dominio"]
            aluno_id = repositorio.criar_aluno(con, aluno["nome"], simulado=True, lacuna_plantada=lacuna)
            sessao_id = repositorio.criar_sessao(con, aluno_id, datetime.now().isoformat(timespec="seconds"))
            n = simular(servico, sessao_id, dominio, rng, aluno["com_ruido"])

            raizes = servico.diagnostico(sessao_id)["diagnostico"]["lacunas_raiz"]
            acertos += raizes[:1] == ([lacuna] if lacuna else [])
            plantada = grafo.nome(lacuna) if lacuna else "(nenhuma)"
            diagnostico = ", ".join(grafo.nome(r) for r in raizes) or "(nenhuma)"
            print(f"{aluno['nome']:<12}{plantada:<22}{n:>9}   {diagnostico}")
    finally:
        con.close()

    print(f"\nTurma criada. O diagnóstico bateu com a lacuna plantada em {acertos} de 30 alunos.")


if __name__ == "__main__":
    main()
