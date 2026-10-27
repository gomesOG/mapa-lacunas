// Tela do professor: mapa de calor (CSS Grid), conceitos críticos, alunos em risco e detalhe.

import { api } from "./api.js";
import {
  NOME_FAIXA, barrasDominio, el, faixa, legenda, linhaDoTempo, mapaDeNomes, mostrarErro,
  painelDiagnostico, pct,
} from "./componentes.js";

const $ = (id) => document.getElementById(id);

let conceitos = [];
let nomes = {};
let limiares = null;
let alunoAberto = null;

// --- Mapa de calor ---

function desenharMapa(mapa) {
  const grade = $("mapa");
  const alunos = mapa.alunos;
  grade.style.gridTemplateColumns = `max-content repeat(${alunos.length}, 24px)`;

  const cabecalho = [el("div", { role: "columnheader" })].concat(
    alunos.map((a) =>
      el("button", {
        class: "rotulo-aluno", type: "button", role: "columnheader", "data-aluno": a.id,
        title: `Abrir diagnóstico de ${a.nome}`, onclick: () => abrirAluno(a.id),
      }, a.nome)),
  );

  const linhas = mapa.conceitos.flatMap((c) => [
    el("div", { class: "rotulo-conceito", role: "rowheader" }, c.nome),
    ...alunos.map((a) => {
      const p = a.estado[c.id];
      const f = faixa(p, limiares, a.classificacao[c.id]);
      return el("button", {
        class: `celula f-${f}`, type: "button", role: "gridcell", "data-aluno": a.id,
        "aria-label": `${a.nome}, ${c.nome}: ${pct(p)} (${NOME_FAIXA[f]})`,
        onclick: () => abrirAluno(a.id),
        onmouseenter: (e) => mostrarDica(e, a.nome, c.nome, p, f),
        onmousemove: moverDica,
        onmouseleave: esconderDica,
      });
    }),
  ]);
  grade.replaceChildren(...cabecalho, ...linhas);
}

function mostrarDica(evento, aluno, conceito, p, f) {
  const dica = $("dica");
  const texto = f === "nao-confirmada"
    ? `${conceito}: p = ${p.toFixed(2)}, lacuna não confirmada (menos de dois erros em questões do conceito)`
    : `${conceito}: p = ${p.toFixed(2)} (${NOME_FAIXA[f]})`;
  dica.replaceChildren(el("strong", {}, aluno), texto);
  dica.hidden = false;
  moverDica(evento);
}

function moverDica(evento) {
  const dica = $("dica");
  const margem = 14;
  const x = Math.min(evento.clientX + margem, window.innerWidth - dica.offsetWidth - 8);
  const y = Math.min(evento.clientY + margem, window.innerHeight - dica.offsetHeight - 8);
  dica.style.left = `${x}px`;
  dica.style.top = `${y}px`;
}

function esconderDica() {
  $("dica").hidden = true;
}

function destacarColuna(alunoId) {
  for (const celula of $("mapa").querySelectorAll("[data-aluno]")) {
    celula.classList.toggle("coluna-ativa", Number(celula.dataset.aluno) === alunoId);
  }
}

// --- Laterais ---

function desenharCriticos(criticos) {
  const relevantes = criticos.filter((c) => c.alunos_com_lacuna > 0);
  if (!relevantes.length) {
    $("criticos").replaceChildren(el("p", { class: "sutil pequeno" }, "Nenhum conceito com lacuna na turma."));
    return;
  }
  $("criticos").replaceChildren(
    ...relevantes.map((c) =>
      el("div", { class: "critico" },
        el("div", { class: "cabeca" },
          el("span", {}, c.nome),
          el("strong", {}, `${Math.round(c.percentual)}%`)),
        el("div", { class: "trilho" }, el("div", { class: "preenchido", style: { width: `${c.percentual}%` } })),
      )),
  );
}

function desenharRisco(risco) {
  if (!risco.length) {
    $("risco").replaceChildren(el("li", { class: "sutil pequeno" }, "Nenhum aluno com lacuna raiz."));
    return;
  }
  $("risco").replaceChildren(
    ...risco.map((a) =>
      el("li", {},
        el("button", { type: "button", onclick: () => abrirAluno(a.id) },
          el("div", { class: "nome" }, a.nome,
            el("span", { class: "contagem" }, `${a.n_lacunas} ${a.n_lacunas === 1 ? "lacuna" : "lacunas"}`)),
          el("div", { class: "chips" }, a.lacunas_raiz_nomes.map((n) => el("span", { class: "chip" }, n))),
        ))),
  );
}

// --- Detalhe do aluno ---

async function abrirAluno(alunoId) {
  alunoAberto = alunoId;
  destacarColuna(alunoId);
  const painel = $("detalhe");
  try {
    const dados = await api.aluno(alunoId);
    if (alunoAberto !== alunoId) return; // outro clique chegou antes
    const { aluno, ultima_sessao: s } = dados;
    $("detalhe-nome").textContent = aluno.nome;
    const partes = [];
    if (s) partes.push(`${s.sessao.n_respondidas} questões na última sessão`);
    if (aluno.simulado) {
      partes.push(`aluno simulado — lacuna plantada: ${aluno.lacuna_plantada ? nomes[aluno.lacuna_plantada] : "nenhuma"}`);
    }
    $("detalhe-info").textContent = partes.join(" · ");
    if (s) {
      $("detalhe-diagnostico").replaceChildren(painelDiagnostico(s.diagnostico, nomes, s.estado));
      $("detalhe-barras").replaceChildren(
        barrasDominio(s.estado, conceitos, s.limiares, s.diagnostico.classificacao));
      $("detalhe-trilha").replaceChildren(linhaDoTempo(s.trilha, nomes));
    } else {
      $("detalhe-diagnostico").replaceChildren(el("p", { class: "sutil" }, "Este aluno ainda não respondeu nenhuma questão."));
      $("detalhe-barras").replaceChildren();
      $("detalhe-trilha").replaceChildren();
    }
  } catch (erro) {
    mostrarErro($("detalhe-diagnostico"), erro);
  }
  painel.hidden = false;
  painel.scrollIntoView({ behavior: "smooth", block: "start" });
  painel.focus({ preventScroll: true });
}

function fecharDetalhe() {
  alunoAberto = null;
  $("detalhe").hidden = true;
  destacarColuna(null);
}

// --- Início ---

async function iniciar() {
  $("fechar-detalhe").addEventListener("click", fecharDetalhe);
  try {
    const [mapa, risco] = await Promise.all([api.mapaTurma(), api.riscoTurma()]);
    conceitos = mapa.conceitos;
    nomes = mapaDeNomes(conceitos);
    limiares = mapa.limiares;
    $("legenda").replaceChildren(legenda(limiares));

    const n = mapa.alunos.length;
    if (!n) {
      $("resumo-turma").textContent = "Nenhum aluno com sessão ainda. Para a demonstração, rode: python scripts/popular_turma.py";
    } else {
      $("resumo-turma").textContent =
        `${n} ${n === 1 ? "aluno" : "alunos"} · ${risco.length} com lacuna raiz`;
    }
    desenharMapa(mapa);
    desenharCriticos(mapa.criticos);
    desenharRisco(risco);
  } catch (erro) {
    mostrarErro($("erro-geral"), erro);
  }
}

iniciar();
