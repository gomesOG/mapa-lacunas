"""Critério de parada, diagnóstico de lacunas e reprodução de uma sessão.

Módulo puro: sem banco, sem arquivos.
"""

from __future__ import annotations

from app.config import (
    ERROS_PARA_LACUNA,
    GANHO_MINIMO,
    LIMIAR_DOMINIO,
    LIMIAR_LACUNA,
    MAX_QUESTOES,
    MIN_QUESTOES,
)
from app.motor.grafo import Grafo
from app.motor.modelo import Crenca, EspacoConhecimento, Estado, atualizar, crenca_inicial
from app.motor.selecao import (
    conceito_em_teste,
    escolher_item,
    ganho_esperado,
    itens_disponiveis,
)

DOMINADO = "dominado"
LACUNA = "lacuna"
INCERTO = "incerto"
NAO_CONFIRMADA = "nao_confirmada"

# Na trilha, além dos conceitos do item, aparecem os que mudaram pelo menos isto (via grafo).
MUDANCA_VISIVEL = 0.01


def classificar(p: float) -> str:
    """'dominado' se p >= LIMIAR_DOMINIO, 'lacuna' se p <= LIMIAR_LACUNA, senão 'incerto'."""
    if p >= LIMIAR_DOMINIO:
        return DOMINADO
    if p <= LIMIAR_LACUNA:
        return LACUNA
    return INCERTO


def deve_parar(
    estado: Estado,
    n_respondidas: int,
    melhor_ganho: float,
    classificacao: dict[str, str] | None = None,
) -> bool:
    """Indica se a sessão deve terminar (seção 6.5 da especificação).

    "Todos classificados" usa a classificação final (classificar_conceitos), quando dada:
    um conceito com lacuna ainda não confirmada mantém a sessão aberta para confirmá-la.
    """
    if n_respondidas >= MAX_QUESTOES:
        return True
    if n_respondidas < MIN_QUESTOES:
        return False
    if melhor_ganho < GANHO_MINIMO:
        return True
    if classificacao is None:
        classificacao = {c: classificar(p) for c, p in estado.items()}
    return all(v in (DOMINADO, LACUNA) for v in classificacao.values())


def erros_por_conceito(respostas: list[tuple[dict, bool]], grafo: Grafo) -> dict[str, int]:
    """Quantas questões erradas exigiam cada conceito (no item ou como pré-requisito).

    Quem erra um item de recursão errou um item que exige também escopo, retorno etc.
    """
    erros = {c: 0 for c in grafo.conceitos}
    for item, acertou in respostas:
        if acertou:
            continue
        exigidos = set(item["conceitos"])
        for c in item["conceitos"]:
            exigidos.update(grafo.ancestrais(c))
        for c in exigidos:
            erros[c] += 1
    return erros


def classificar_conceitos(estado: Estado, grafo: Grafo, erros: dict[str, int] | None = None) -> dict[str, str]:
    """Classificação de cada conceito, em ordem topológica.

    Com erros (ver erros_por_conceito), um p baixo só vira 'lacuna' depois de pelo menos
    ERROS_PARA_LACUNA erros em questões que exigem o conceito, ou se ele depender de uma
    lacuna já confirmada (quem não domina variável não domina recursão). Antes disso o
    conceito fica 'nao_confirmada': um erro isolado pode ser só um deslize, e um p baixo
    sem erro nenhum vem só da estimativa inicial. Com erros=None, vale só o p.
    """
    classificacao = {c: classificar(estado[c]) for c in grafo.ordem_topologica()}
    if erros is None:
        return classificacao
    confirmadas = {c for c, v in classificacao.items() if v == LACUNA and erros[c] >= ERROS_PARA_LACUNA}
    for c, v in classificacao.items():
        if v == LACUNA and c not in confirmadas:
            herdada = any(a in confirmadas for a in grafo.ancestrais(c))
            classificacao[c] = LACUNA if herdada else NAO_CONFIRMADA
    return classificacao


def conceitos_a_confirmar(estado: Estado, grafo: Grafo, erros: dict[str, int]) -> list[str]:
    """Lacunas com algum erro, mas ainda abaixo de ERROS_PARA_LACUNA (a mais grave primeiro)."""
    classificacao = classificar_conceitos(estado, grafo, erros)
    pendentes = [c for c, v in classificacao.items() if v == NAO_CONFIRMADA and erros[c] >= 1]
    ordem = grafo.ordem_topologica()
    return sorted(pendentes, key=lambda c: (estado[c], ordem.index(c)))


def escolher_proxima(
    crenca: Crenca,
    itens: list[dict],
    respondidos: set[str],
    erros: dict[str, int],
) -> tuple[dict | None, float, str | None]:
    """Política adaptativa: (item, ganho, conceito em confirmação ou None).

    Se há lacuna a confirmar, escolhe, entre os itens que testam diretamente esse conceito,
    o de maior ganho esperado. Senão (ou se esses itens acabaram), o de maior ganho geral.
    """
    grafo = crenca.espaco.grafo
    for c in conceitos_a_confirmar(crenca.estado, grafo, erros):
        do_conceito = [item for item in itens if c in item["conceitos"]]
        item, ganho = escolher_item(crenca, do_conceito, respondidos)
        if item is not None:
            return item, ganho, c
    item, ganho = escolher_item(crenca, itens, respondidos)
    return item, ganho, None


def lacunas_raiz(estado: Estado, grafo: Grafo, erros: dict[str, int] | None = None) -> list[str]:
    """Conceitos com lacuna cujos pré-requisitos (diretos e indiretos) não têm lacuna.

    Se um pré-requisito também está com lacuna, a causa está mais embaixo no grafo
    e quem é reportado é ele. Ordenadas por p crescente (a mais grave primeiro).
    """
    classificacao = classificar_conceitos(estado, grafo, erros)
    com_lacuna = {c for c, v in classificacao.items() if v == LACUNA}
    raizes = [
        c for c in com_lacuna
        if not any(a in com_lacuna for a in grafo.ancestrais(c))
    ]
    ordem = grafo.ordem_topologica()
    return sorted(raizes, key=lambda c: (estado[c], ordem.index(c)))


def recomendar(grafo: Grafo, raiz: str, classificacao: dict[str, str]) -> dict:
    """Recomendação para uma lacuna raiz: o que revisar e o que isso destrava."""
    destravar = [d for d in grafo.descendentes(raiz) if classificacao[d] != DOMINADO]
    return {
        "conceito": raiz,
        "texto": f"Revisar {grafo.nome(raiz)}",
        "destravar": destravar,
    }


def diagnosticar(estado: Estado, grafo: Grafo, erros: dict[str, int] | None = None) -> dict:
    """{'situacao': 'lacunas'|'sem_lacunas'|'inconclusivo',
        'lacunas_raiz': [...], 'recomendacoes': [...], 'classificacao': {c: '...'}}

    'sem_lacunas' só quando todos os conceitos estão dominados; se não há lacuna mas há
    conceitos incertos ou com lacuna não confirmada, o diagnóstico é 'inconclusivo'.
    """
    classificacao = classificar_conceitos(estado, grafo, erros)
    raizes = lacunas_raiz(estado, grafo, erros)
    if raizes:
        situacao = "lacunas"
    elif all(v == DOMINADO for v in classificacao.values()):
        situacao = "sem_lacunas"
    else:
        situacao = "inconclusivo"
    return {
        "situacao": situacao,
        "lacunas_raiz": raizes,
        "recomendacoes": [recomendar(grafo, r, classificacao) for r in raizes],
        "classificacao": classificacao,
    }


def crenca_apos(
    respostas: list[tuple[str, bool]],
    itens: list[dict],
    espaco: EspacoConhecimento,
) -> Crenca:
    """Crença depois das respostas, sem montar a trilha (mais barato)."""
    crenca = crenca_inicial(espaco)
    for item, acertou in _validar_respostas(respostas, itens):
        crenca = atualizar(crenca, item["conceitos"], acertou)
    return crenca


def reproduzir(
    respostas: list[tuple[str, bool]],
    itens: list[dict],
    espaco: EspacoConhecimento,
) -> tuple[Crenca, list[dict]]:
    """Recalcula a crença e a trilha de raciocínio a partir das respostas, em ordem.

    respostas: [(item_id, acertou), ...] na ordem em que foram dadas.
    A crença parte da priori; o banco guarda só as respostas. O estado {conceito: p}
    é crenca.estado.
    """
    crenca = crenca_inicial(espaco)
    anteriores: list[tuple[dict, bool]] = []
    trilha: list[dict] = []

    for ordem, (item, acertou) in enumerate(_validar_respostas(respostas, itens), start=1):
        antes = crenca.estado
        respondidos = {i["id"] for i, _ in anteriores}
        erros = erros_por_conceito(anteriores, espaco.grafo)
        motivo = _motivo_escolha(crenca, item, itens, respondidos, erros)
        ganho = ganho_esperado(crenca, item["conceitos"])
        crenca = atualizar(crenca, item["conceitos"], acertou)
        depois = crenca.estado

        trilha.append({
            "ordem": ordem,
            "item_id": item["id"],
            "acertou": acertou,
            "conceito_em_teste": conceito_em_teste(antes, item["conceitos"]),
            "ganho": round(ganho, 4),
            "mudancas": _mudancas(antes, depois, item["conceitos"]),
            "motivo_escolha": motivo,
        })
        anteriores.append((item, acertou))

    return crenca, trilha


def _validar_respostas(respostas: list[tuple[str, bool]], itens: list[dict]) -> list[tuple[dict, bool]]:
    """Troca ids por itens, recusando item desconhecido ou repetido."""
    por_id = {item["id"]: item for item in itens}
    vistos: set[str] = set()
    resultado = []
    for ordem, (item_id, acertou) in enumerate(respostas, start=1):
        if item_id not in por_id:
            raise ValueError(f"Item desconhecido na resposta {ordem}: '{item_id}'")
        if item_id in vistos:
            raise ValueError(f"Item '{item_id}' respondido duas vezes")
        vistos.add(item_id)
        resultado.append((por_id[item_id], bool(acertou)))
    return resultado


def _mudancas(antes: Estado, depois: Estado, conceitos_item: list[str]) -> list[dict]:
    """Conceitos do item primeiro; depois os que mudaram de forma visível pelo grafo."""
    do_item = list(dict.fromkeys(conceitos_item))
    pelo_grafo = [
        c for c in antes
        if c not in do_item and abs(depois[c] - antes[c]) >= MUDANCA_VISIVEL
    ]
    return [
        {"conceito": c, "antes": round(antes[c], 4), "depois": round(depois[c], 4), "no_item": c in do_item}
        for c in do_item + pelo_grafo
    ]


def _motivo_escolha(
    crenca: Crenca,
    item: dict,
    itens: list[dict],
    respondidos: set[str],
    erros: dict[str, int],
) -> str:
    """Explica por que este item foi apresentado, comparando com a escolha da política adaptativa."""
    escolhido, ganho_escolhido, confirmando = escolher_proxima(crenca, itens, respondidos, erros)
    if escolhido is not None and escolhido["id"] == item["id"] and confirmando:
        nome = crenca.espaco.grafo.nome(confirmando)
        n = len(itens_disponiveis([i for i in itens if confirmando in i["conceitos"]], respondidos))
        e = erros[confirmando]
        return (
            f"confirmar a lacuna em {nome} ({e} {'erro' if e == 1 else 'erros'} até aqui; são precisos "
            f"{ERROS_PARA_LACUNA}): maior ganho esperado ({ganho_escolhido:.2f} bits) "
            f"entre {n} {'item que testa' if n == 1 else 'itens que testam'} o conceito"
        )
    n = len(itens_disponiveis(itens, respondidos))
    entre = f"entre {n} {'item' if n == 1 else 'itens'}"
    melhor, melhor_ganho = escolher_item(crenca, itens, respondidos)
    if melhor is not None and melhor["id"] == item["id"]:
        return f"maior ganho esperado ({melhor_ganho:.2f} bits) {entre}"
    ganho = ganho_esperado(crenca, item["conceitos"])
    return (
        f"ganho esperado de {ganho:.2f} bits; o maior disponível era "
        f"{melhor_ganho:.2f} bits ({melhor['id']}) {entre}"
    )
