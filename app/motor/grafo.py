"""Grafo de pré-requisitos entre conceitos (DAG).

A aresta A -> B significa "A é pré-requisito de B".
Módulo puro: recebe a lista de conceitos já carregada, não lê arquivos.
"""

from __future__ import annotations


class Grafo:
    """Grafo de pré-requisitos já validado (sem ciclos, sem referências soltas)."""

    def __init__(
        self,
        nomes: dict[str, str],
        prereqs: dict[str, list[str]],
        ordem: list[str],
    ) -> None:
        self._nomes = nomes
        self._prereqs = prereqs
        self._ordem = ordem
        self._posicao = {c: i for i, c in enumerate(ordem)}
        self._dependentes: dict[str, list[str]] = {c: [] for c in ordem}
        for c in ordem:
            for p in prereqs[c]:
                self._dependentes[p].append(c)

    @property
    def conceitos(self) -> list[str]:
        """Todos os conceitos, em ordem topológica."""
        return list(self._ordem)

    def nome(self, c: str) -> str:
        """Nome legível do conceito."""
        self._checar(c)
        return self._nomes[c]

    def prerequisitos(self, c: str) -> list[str]:
        """Pré-requisitos diretos de c."""
        self._checar(c)
        return list(self._prereqs[c])

    def dependentes(self, c: str) -> list[str]:
        """Conceitos que têm c como pré-requisito direto."""
        self._checar(c)
        return list(self._dependentes[c])

    def ancestrais(self, c: str) -> list[str]:
        """Todos os pré-requisitos de c, diretos e indiretos, em ordem topológica."""
        self._checar(c)
        return self._ordenar(self._alcancaveis(c, self._prereqs))

    def descendentes(self, c: str) -> list[str]:
        """Todos os conceitos que dependem de c, direta ou indiretamente, em ordem topológica."""
        self._checar(c)
        return self._ordenar(self._alcancaveis(c, self._dependentes))

    def ordem_topologica(self) -> list[str]:
        """Conceitos da base para o topo: todo pré-requisito vem antes de quem depende dele."""
        return list(self._ordem)

    def _alcancaveis(self, inicio: str, vizinhos: dict[str, list[str]]) -> set[str]:
        visitados: set[str] = set()
        pilha = list(vizinhos[inicio])
        while pilha:
            atual = pilha.pop()
            if atual not in visitados:
                visitados.add(atual)
                pilha.extend(vizinhos[atual])
        return visitados

    def _ordenar(self, conjunto: set[str]) -> list[str]:
        return sorted(conjunto, key=self._posicao.__getitem__)

    def _checar(self, c: str) -> None:
        if c not in self._nomes:
            raise KeyError(f"Conceito desconhecido: '{c}'")


def carregar_grafo(conceitos: list[dict]) -> Grafo:
    """Valida a lista de conceitos e monta o grafo.

    Lança ValueError se houver id repetido, pré-requisito inexistente ou ciclo.
    """
    nomes: dict[str, str] = {}
    prereqs: dict[str, list[str]] = {}
    for conceito in conceitos:
        cid = conceito.get("id")
        if not cid:
            raise ValueError(f"Conceito sem 'id': {conceito}")
        if cid in nomes:
            raise ValueError(f"Conceito repetido: '{cid}'")
        nomes[cid] = conceito.get("nome", cid)
        prereqs[cid] = list(conceito.get("prerequisitos", []))

    for cid, lista in prereqs.items():
        for p in lista:
            if p not in nomes:
                raise ValueError(f"O conceito '{cid}' tem pré-requisito inexistente: '{p}'")
            if p == cid:
                raise ValueError(f"O conceito '{cid}' é pré-requisito de si mesmo")
        if len(set(lista)) != len(lista):
            raise ValueError(f"O conceito '{cid}' tem pré-requisito repetido")

    ordem = _ordenar_topologicamente(list(nomes), prereqs)
    return Grafo(nomes, prereqs, ordem)


def _ordenar_topologicamente(ids: list[str], prereqs: dict[str, list[str]]) -> list[str]:
    """Algoritmo de Kahn. Entre conceitos prontos, mantém a ordem de entrada (determinístico)."""
    pendentes = {c: len(prereqs[c]) for c in ids}
    dependentes: dict[str, list[str]] = {c: [] for c in ids}
    for c in ids:
        for p in prereqs[c]:
            dependentes[p].append(c)

    ordem: list[str] = []
    prontos = [c for c in ids if pendentes[c] == 0]
    while prontos:
        atual = min(prontos, key=ids.index)
        prontos.remove(atual)
        ordem.append(atual)
        for d in dependentes[atual]:
            pendentes[d] -= 1
            if pendentes[d] == 0:
                prontos.append(d)

    if len(ordem) < len(ids):
        restantes = [c for c in ids if c not in ordem]
        ciclo = _encontrar_ciclo(restantes, prereqs)
        raise ValueError("Ciclo de pré-requisitos detectado: " + " -> ".join(ciclo))
    return ordem


def _encontrar_ciclo(restantes: list[str], prereqs: dict[str, list[str]]) -> list[str]:
    """Segue pré-requisitos entre os conceitos que sobraram até repetir um (isso é o ciclo)."""
    sobra = set(restantes)
    caminho = [restantes[0]]
    while True:
        proximo = next(p for p in prereqs[caminho[-1]] if p in sobra)
        if proximo in caminho:
            ciclo = caminho[caminho.index(proximo):] + [proximo]
            return list(reversed(ciclo))
        caminho.append(proximo)
