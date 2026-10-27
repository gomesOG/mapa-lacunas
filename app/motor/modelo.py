"""Modelo de resposta DINA sobre os estados de conhecimento viáveis do grafo.

DINA: o aluno só acerta "de verdade" se dominar TODOS os conceitos do item.
Fora isso, pode acertar por chute (CHUTE) ou errar por deslize (DESLIZE).

Estados viáveis (Teoria dos Espaços de Conhecimento): um estado é o conjunto de
conceitos que o aluno domina, e só são viáveis os estados fechados por
pré-requisito (quem domina recursão domina escopo). No grafo do projeto são 345
estados, contra 32.768 combinações livres.

A crença sobre o aluno é uma distribuição de probabilidade sobre esses estados.
O "estado" exibido ({conceito: p}) é a marginal: p é a soma das probabilidades
dos estados que contêm o conceito. Uma resposta sobre um conceito também informa
sobre seus pré-requisitos e dependentes, porque o grafo amarra os conceitos.

Módulo puro: sem banco, sem arquivos.
"""

from __future__ import annotations

from app.config import CHUTE, DESLIZE, PRIORI
from app.motor.grafo import Grafo

Estado = dict[str, float]


class EspacoConhecimento:
    """Os estados de conhecimento viáveis de um grafo, com índices pré-calculados."""

    def __init__(self, grafo: Grafo) -> None:
        self.grafo = grafo
        self.conceitos = grafo.ordem_topologica()
        self.estados: list[frozenset[str]] = _enumerar_estados(grafo)
        self._indices: dict[frozenset[str], tuple[int, ...]] = {}

    def indices_com(self, conceitos: frozenset[str]) -> tuple[int, ...]:
        """Posições dos estados que contêm todos os conceitos dados (memorizado)."""
        if conceitos not in self._indices:
            desconhecidos = conceitos - set(self.conceitos)
            if desconhecidos:
                raise KeyError(f"Conceito desconhecido: {', '.join(sorted(desconhecidos))}")
            self._indices[conceitos] = tuple(
                i for i, estado in enumerate(self.estados) if conceitos <= estado
            )
        return self._indices[conceitos]


class Crenca:
    """Distribuição de probabilidade sobre os estados viáveis. Imutável."""

    def __init__(self, espaco: EspacoConhecimento, pesos: tuple[float, ...]) -> None:
        self.espaco = espaco
        self.pesos = pesos
        self._estado: Estado | None = None

    @property
    def estado(self) -> Estado:
        """Probabilidade de domínio de cada conceito, em ordem topológica."""
        if self._estado is None:
            self._estado = {c: self.massa({c}) for c in self.espaco.conceitos}
        return dict(self._estado)

    def massa(self, conceitos: set[str] | frozenset[str]) -> float:
        """Probabilidade de o aluno dominar todos os conceitos dados."""
        indices = self.espaco.indices_com(frozenset(conceitos))
        return sum(map(self.pesos.__getitem__, indices))


def montar_espaco(grafo: Grafo) -> EspacoConhecimento:
    """Enumera os estados viáveis do grafo."""
    return EspacoConhecimento(grafo)


def crenca_inicial(espaco: EspacoConhecimento, priori: float | Estado = PRIORI) -> Crenca:
    """Crença antes de qualquer resposta (rede bayesiana sobre o grafo).

    priori (PRIORI ou um valor por conceito) é a chance de o aluno dominar um conceito
    DADO QUE domina todos os pré-requisitos dele. Um conceito cujo pré-requisito falta
    fica de fora por consequência e não pesa no estado: assim, não dominar a base não é
    tratado como "15 lacunas independentes", e sim como uma lacuna só.
    Sem pré-requisitos, isso se reduz a conceitos independentes com p = priori.
    """
    p = priori if isinstance(priori, dict) else {c: priori for c in espaco.conceitos}
    pesos = []
    for estado in espaco.estados:
        peso = 1.0
        for c in espaco.conceitos:
            if set(espaco.grafo.prerequisitos(c)) <= estado:
                peso *= p[c] if c in estado else 1.0 - p[c]
        pesos.append(peso)
    return Crenca(espaco, _normalizar(pesos))


def prob_acerto(
    crenca: Crenca,
    conceitos_item: list[str],
    deslize: float = DESLIZE,
    chute: float = CHUTE,
) -> float:
    """Probabilidade de o aluno acertar um item que exige os conceitos dados."""
    domina_tudo = crenca.massa(_conjunto(conceitos_item))
    return domina_tudo * (1.0 - deslize) + (1.0 - domina_tudo) * chute


def atualizar(
    crenca: Crenca,
    conceitos_item: list[str],
    acertou: bool,
    deslize: float = DESLIZE,
    chute: float = CHUTE,
) -> Crenca:
    """Retorna uma NOVA crença após observar a resposta (regra de Bayes). Não modifica a original."""
    exigidos = _conjunto(conceitos_item)
    v_domina, v_nao = _verossimilhancas(acertou, deslize, chute)
    pesos = [
        peso * (v_domina if exigidos <= estado else v_nao)
        for peso, estado in zip(crenca.pesos, crenca.espaco.estados)
    ]
    return Crenca(crenca.espaco, _normalizar(pesos))


def estado_apos(
    crenca: Crenca,
    conceitos_item: list[str],
    acertou: bool,
    deslize: float = DESLIZE,
    chute: float = CHUTE,
) -> Estado:
    """Marginais que resultariam da resposta, sem montar a nova crença inteira.

    Dá o mesmo resultado que atualizar(...).estado; é o atalho usado na seleção,
    que precisa simular as duas respostas possíveis para cada item candidato.
    """
    exigidos = _conjunto(conceitos_item)
    v_domina, v_nao = _verossimilhancas(acertou, deslize, chute)
    m_item = crenca.massa(exigidos)
    total = v_domina * m_item + v_nao * (1.0 - m_item)

    atual = crenca.estado
    novo = {}
    for c, p in atual.items():
        com_item = crenca.massa(exigidos | {c})   # domina c e todo o item
        novo[c] = (v_domina * com_item + v_nao * (p - com_item)) / total
    return novo


def _verossimilhancas(acertou: bool, deslize: float, chute: float) -> tuple[float, float]:
    """(P(resposta | domina o item), P(resposta | não domina o item))."""
    if acertou:
        return 1.0 - deslize, chute
    return deslize, 1.0 - chute


def _enumerar_estados(grafo: Grafo) -> list[frozenset[str]]:
    """Todos os conjuntos de conceitos fechados por pré-requisito, incluindo o vazio."""
    ordem = grafo.ordem_topologica()
    estados: list[frozenset[str]] = []

    def expandir(i: int, atual: frozenset[str]) -> None:
        if i == len(ordem):
            estados.append(atual)
            return
        c = ordem[i]
        expandir(i + 1, atual)
        if all(p in atual for p in grafo.prerequisitos(c)):
            expandir(i + 1, atual | {c})

    expandir(0, frozenset())
    return estados


def _normalizar(pesos: list[float]) -> tuple[float, ...]:
    total = sum(pesos)
    return tuple(p / total for p in pesos)


def _conjunto(conceitos_item: list[str]) -> frozenset[str]:
    if not conceitos_item:
        raise ValueError("O item precisa exigir ao menos um conceito")
    return frozenset(conceitos_item)
