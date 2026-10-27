// Peças de tela usadas pelo aluno e pelo professor: barras, diagnóstico e linha do tempo.
// Todo texto vindo do servidor entra por textContent (nunca innerHTML).

/** Cria um elemento: el("div", { class: "x", onclick: f }, "texto", outroElemento). */
export function el(tag, props = {}, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [chave, valor] of Object.entries(props)) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (chave.startsWith("on")) elemento.addEventListener(chave.slice(2), valor);
    else if (chave === "class") elemento.className = valor;
    else if (chave === "style") Object.assign(elemento.style, valor);
    else elemento.setAttribute(chave, valor === true ? "" : valor);
  }
  for (const filho of filhos.flat()) {
    if (filho === null || filho === undefined || filho === false) continue;
    elemento.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  }
  return elemento;
}

const MEIO = 0.5; // divisa visual entre "médio" e "alerta" (só para as cores)

/** Faixa de cor do valor p: domina, medio, alerta, lacuna ou nao-confirmada.
 *  classe é a classificação vinda do servidor; "nao_confirmada" = p baixo, mas com menos
 *  erros do que o necessário para declarar lacuna (pode ser só deslize ou só a estimativa inicial). */
export function faixa(p, limiares, classe) {
  if (classe === "nao_confirmada") return "nao-confirmada";
  if (p >= limiares.dominio) return "domina";
  if (p >= MEIO) return "medio";
  if (p > limiares.lacuna) return "alerta";
  return "lacuna";
}

export const NOME_FAIXA = {
  domina: "domina", medio: "médio", alerta: "alerta", lacuna: "lacuna",
  "nao-confirmada": "lacuna não confirmada",
};

const EXPLICA_NAO_CONFIRMADA =
  "Estimativa baixa, mas com menos de dois erros em questões que exigem o conceito: ainda não é lacuna.";

export function pct(p) {
  return `${Math.round(p * 100)}%`;
}

export function legenda(limiares) {
  const amostra = (f, texto) => el("span", {}, el("span", { class: `amostra f-${f}` }), texto);
  return el("div", { class: "legenda", "aria-label": "Legenda de cores" },
    amostra("domina", `domina (≥ ${pct(limiares.dominio)})`),
    amostra("medio", `médio (${pct(MEIO)}–${pct(limiares.dominio)})`),
    amostra("alerta", `alerta (${pct(limiares.lacuna)}–${pct(MEIO)})`),
    amostra("lacuna", `lacuna (≤ ${pct(limiares.lacuna)})`),
    el("span", { title: EXPLICA_NAO_CONFIRMADA },
      el("span", { class: "amostra f-nao-confirmada" }), "não confirmada"),
  );
}

/** Uma barra de domínio por conceito, na ordem dada. */
export function barrasDominio(estado, conceitos, limiares, classificacao = {}) {
  return el("div", { class: "barras" },
    conceitos.map((c) => {
      const p = estado[c.id];
      const f = faixa(p, limiares, classificacao[c.id]);
      const naoConfirmada = f === "nao-confirmada";
      return el("div", { class: "barra", title: `${c.nome}: ${pct(p)}${naoConfirmada ? ` — ${EXPLICA_NAO_CONFIRMADA}` : ""}` },
        el("span", {}, c.nome),
        el("div", { class: "trilho" },
          el("div", { class: `preenchido f-${f}`, style: { width: naoConfirmada ? "100%" : `${Math.max(p * 100, 1)}%` } })),
        el("span", { class: "valor" }, naoConfirmada ? `${pct(p)}?` : pct(p)),
      );
    }),
  );
}

/** Lacunas raiz em destaque, com a recomendação; ou a mensagem de sem lacunas / inconclusivo. */
export function painelDiagnostico(diagnostico, nomes, estado) {
  if (diagnostico.situacao === "lacunas") {
    return el("div", {},
      diagnostico.recomendacoes.map((r, i) =>
        el("div", { class: "destaque-lacuna" },
          el("div", { class: "pequeno sutil" }, i === 0 ? "Lacuna raiz principal" : "Outra lacuna raiz"),
          el("div", { class: "titulo" }, `${nomes[r.conceito]} (${pct(estado[r.conceito])})`),
          el("div", {}, r.texto + "."),
          r.destravar.length
            ? el("div", { class: "pequeno" }, "Isso destrava: ", r.destravar.map((d) => nomes[d]).join(", "), ".")
            : null,
        )),
    );
  }
  if (diagnostico.situacao === "sem_lacunas") {
    return el("div", { class: "destaque-lacuna destaque-ok" },
      el("div", { class: "titulo" }, "Nenhuma lacuna encontrada"),
      el("div", {}, "Todos os conceitos foram classificados como dominados."));
  }
  const pendentes = Object.entries(diagnostico.classificacao)
    .filter(([, v]) => v === "incerto" || v === "nao_confirmada")
    .map(([c]) => nomes[c]);
  return el("div", { class: "destaque-lacuna destaque-incerto" },
    el("div", { class: "titulo" }, "Nenhuma lacuna encontrada até aqui"),
    el("div", {}, "O diagnóstico é inconclusivo: alguns conceitos ficaram incertos ou não foram testados."),
    pendentes.length ? el("div", { class: "pequeno" }, "Ainda sem conclusão: ", pendentes.join(", "), ".") : null);
}

function chipMudanca(m, nomes) {
  const desceu = m.depois < m.antes;
  return el("span", { class: `mudanca${m.no_item ? " no-item" : ""}` },
    `${nomes[m.conceito]} ${pct(m.antes)} → ${pct(m.depois)} `,
    el("span", { class: desceu ? "seta-baixo" : "seta-cima", "aria-label": desceu ? "caiu" : "subiu" },
      desceu ? "↓" : "↑"),
  );
}

/** Linha do tempo do raciocínio: para cada questão, o que mudou e por quê. */
export function linhaDoTempo(trilha, nomes) {
  if (!trilha.length) return el("p", { class: "sutil" }, "Nenhuma questão respondida.");
  return el("ol", { class: "tempo" },
    trilha.map((passo) => {
      const doItem = passo.mudancas.filter((m) => m.no_item);
      const peloGrafo = passo.mudancas.filter((m) => !m.no_item);
      return el("li", { class: `passo ${passo.acertou ? "acertou" : "errou"}` },
        el("span", { class: "marcador", "aria-hidden": "true" }, passo.ordem),
        el("div", { class: "resumo" },
          `Questão ${passo.ordem} (${passo.item_id}) — ${passo.acertou ? "acertou" : "errou"}`,
          el("span", { class: "sutil" }, ` · em teste: ${nomes[passo.conceito_em_teste]}`)),
        el("div", { class: "motivo" }, `Por que esta questão: ${passo.motivo_escolha}.`),
        el("div", { class: "mudancas" }, doItem.map((m) => chipMudanca(m, nomes))),
        peloGrafo.length
          ? el("div", { class: "mudancas", style: { marginTop: "6px" } },
              el("span", { class: "pequeno sutil" }, "pelo grafo:"),
              peloGrafo.map((m) => chipMudanca(m, nomes)))
          : null,
      );
    }),
  );
}

/** Mapa {id: nome} a partir da lista de conceitos. */
export function mapaDeNomes(conceitos) {
  return Object.fromEntries(conceitos.map((c) => [c.id, c.nome]));
}

export function mostrarErro(container, erro) {
  container.replaceChildren(el("div", { class: "erro", role: "alert" }, erro.message || String(erro)));
}
