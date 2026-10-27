// Funções fetch compartilhadas pelas telas do aluno e do professor.

async function requisitar(metodo, rota, corpo) {
  const opcoes = { method: metodo, headers: {} };
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  let resposta;
  try {
    resposta = await fetch(rota, opcoes);
  } catch {
    throw new Error("Não foi possível falar com o servidor. Ele está rodando?");
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    const detalhe = typeof dados.detail === "string" ? dados.detail : `Erro ${resposta.status}`;
    throw new Error(detalhe);
  }
  return dados;
}

export const api = {
  conceitos: () => requisitar("GET", "/api/conceitos"),
  iniciarSessao: (nome) => requisitar("POST", "/api/sessoes", { nome }),
  proximo: (sessaoId) => requisitar("GET", `/api/sessoes/${sessaoId}/proximo`),
  responder: (sessaoId, itemId, opcao) =>
    requisitar("POST", `/api/sessoes/${sessaoId}/respostas`, { item_id: itemId, opcao }),
  diagnostico: (sessaoId) => requisitar("GET", `/api/sessoes/${sessaoId}/diagnostico`),
  mapaTurma: () => requisitar("GET", "/api/turma/mapa"),
  riscoTurma: () => requisitar("GET", "/api/turma/risco"),
  aluno: (alunoId) => requisitar("GET", `/api/alunos/${alunoId}`),
};
