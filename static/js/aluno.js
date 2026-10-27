// Tela do aluno: nome -> questões uma a uma -> diagnóstico com a linha do tempo do raciocínio.

import { api } from "./api.js";
import {
  barrasDominio, el, legenda, linhaDoTempo, mapaDeNomes, mostrarErro, painelDiagnostico,
} from "./componentes.js";

const CHAVE_SESSAO = "mapa-lacunas:sessao";
const LETRAS = ["A", "B", "C", "D"];
const $ = (id) => document.getElementById(id);

let conceitos = [];
let nomes = {};
let sessaoId = null;
let questaoAtual = null;

function mostrarTela(id) {
  for (const tela of ["tela-inicio", "tela-questao", "tela-final"]) $(tela).hidden = tela !== id;
  window.scrollTo({ top: 0 });
}

// Guardar a sessão só serve para recarregar a página sem perder o lugar.
function lembrarSessao(id) {
  try {
    if (id === null) sessionStorage.removeItem(CHAVE_SESSAO);
    else sessionStorage.setItem(CHAVE_SESSAO, String(id));
  } catch { /* sem armazenamento: segue sem lembrar */ }
}

function sessaoLembrada() {
  try {
    return sessionStorage.getItem(CHAVE_SESSAO);
  } catch {
    return null;
  }
}

async function comecar(evento) {
  evento.preventDefault();
  const nome = $("nome").value.trim();
  if (!nome) return;
  const botao = evento.submitter;
  if (botao) botao.disabled = true;
  try {
    sessaoId = (await api.iniciarSessao(nome)).sessao_id;
    lembrarSessao(sessaoId);
    await carregarProxima();
  } catch (erro) {
    mostrarErro($("erro-inicio"), erro);
  } finally {
    if (botao) botao.disabled = false;
  }
}

async function carregarProxima() {
  $("erro-questao").replaceChildren();
  const prox = await api.proximo(sessaoId);
  if (prox.fim) {
    await mostrarFinal();
    return;
  }
  questaoAtual = prox.item;
  $("em-teste").textContent = `Em teste: ${prox.conceito_em_teste.nome}`;
  $("contador").textContent = `questão ${prox.ordem}`;
  $("enunciado").textContent = prox.item.enunciado;
  $("codigo").textContent = prox.item.codigo;
  $("retorno").hidden = true;
  $("opcoes").replaceChildren(
    ...prox.item.opcoes.map((texto, i) =>
      el("button", { class: "opcao", type: "button", "data-indice": i, onclick: () => responder(i) },
        el("span", { class: "letra" }, LETRAS[i]), el("span", {}, texto))),
  );
  mostrarTela("tela-questao");
  $("opcoes").querySelector("button")?.focus();
}

async function responder(indice) {
  const botoes = [...$("opcoes").querySelectorAll("button")];
  botoes.forEach((b) => { b.disabled = true; });
  try {
    const r = await api.responder(sessaoId, questaoAtual.id, indice);
    botoes[r.correta].classList.add("correta");
    if (!r.acertou) botoes[indice].classList.add("errada");
    $("retorno").classList.toggle("errou", !r.acertou);
    $("retorno-titulo").textContent = r.acertou
      ? "Acertou!"
      : `Não foi dessa vez. A resposta certa é a ${LETRAS[r.correta]}.`;
    $("retorno-explicacao").textContent = r.explicacao;
    $("retorno").hidden = false;
    $("botao-proxima").focus();
  } catch (erro) {
    botoes.forEach((b) => { b.disabled = false; });
    mostrarErro($("erro-questao"), erro);
  }
}

async function avancar() {
  $("botao-proxima").disabled = true;
  try {
    await carregarProxima();
  } catch (erro) {
    mostrarErro($("erro-questao"), erro);
  } finally {
    $("botao-proxima").disabled = false;
  }
}

async function mostrarFinal() {
  const d = await api.diagnostico(sessaoId);
  const n = d.sessao.n_respondidas;
  $("final-resumo").textContent =
    `${d.aluno.nome}, você respondeu ${n} ${n === 1 ? "questão" : "questões"}.`;
  $("final-diagnostico").replaceChildren(painelDiagnostico(d.diagnostico, nomes, d.estado));
  $("final-legenda").replaceChildren(legenda(d.limiares));
  $("final-barras").replaceChildren(barrasDominio(d.estado, conceitos, d.limiares, d.diagnostico.classificacao));
  $("final-trilha").replaceChildren(linhaDoTempo(d.trilha, nomes));
  mostrarTela("tela-final");
}

function novaSessao() {
  sessaoId = null;
  lembrarSessao(null);
  $("nome").value = "";
  mostrarTela("tela-inicio");
  $("nome").focus();
}

async function iniciar() {
  $("form-inicio").addEventListener("submit", comecar);
  $("botao-proxima").addEventListener("click", avancar);
  $("botao-nova").addEventListener("click", novaSessao);
  try {
    conceitos = await api.conceitos();
    nomes = mapaDeNomes(conceitos);
    const lembrada = sessaoLembrada();
    if (lembrada) {
      sessaoId = Number(lembrada);
      await carregarProxima();
    }
  } catch (erro) {
    lembrarSessao(null);
    mostrarTela("tela-inicio");
    mostrarErro($("erro-inicio"), erro);
  }
}

iniciar();
