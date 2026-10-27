# Detalhes técnicos

Complemento do [README](../README.md): o funcionamento do motor em detalhe, a API, as decisões de projeto e a revisão pedagógica pendente.

---

## O motor, passo a passo

Todo o motor fica em `app/motor/` e é **puro**: funções sem banco, sem arquivo e sem rede, que recebem dados e devolvem dados. As constantes ficam todas em `app/config.py`.

1. **Grafo de pré-requisitos** (`grafo.py`). São 15 conceitos num grafo acíclico (DAG); a aresta A → B significa "A é pré-requisito de B". A carga recusa ciclos e pré-requisitos inexistentes.
2. **Estados de conhecimento viáveis** (`modelo.py`). Um estado é o conjunto de conceitos que o aluno domina. Só valem os estados fechados por pré-requisito. No grafo do projeto são **345 estados**.
3. **Crença inicial em rede bayesiana.** `PRIORI = 0,60` é a chance de dominar um conceito **dado que domina seus pré-requisitos**. Por isso a estimativa inicial cai com a profundidade no grafo: variável começa em 0,60 e recursão em 0,02.
4. **Modelo de resposta DINA.** O aluno só acerta "de verdade" se dominar todos os conceitos do item. Fora isso, acerta por chute (`CHUTE = 0,25`) ou erra por deslize (`DESLIZE = 0,10`). A estimativa exibida, p, é a soma das probabilidades dos estados que contêm o conceito.
5. **Escolha da próxima questão** (`selecao.py` e `diagnostico.escolher_proxima`).
   - Normalmente vem o item com maior ganho de informação esperado, isto é, a queda esperada na soma das entropias de todos os conceitos. Em empate, vence o item com menos conceitos e depois o menor id.
   - **Confirmação:** se um conceito está com p de lacuna e já tem um erro, a próxima questão é a de maior ganho entre as que testam diretamente esse conceito.
6. **Parada.** A sessão para em 15 questões, ou a partir de 6 se nenhuma questão traz ganho maior que 0,01 bit ou se todos os conceitos estão classificados. Uma lacuna ainda não confirmada mantém a sessão aberta.
7. **Classificação:**
   - p ≥ 0,70 é **dominado**; p ≤ 0,30 é lacuna em potencial; o resto é **incerto**.
   - A lacuna só é declarada depois de `ERROS_PARA_LACUNA = 2` erros em questões que exigem o conceito, ou se ele depende de uma lacuna já confirmada.
   - Antes disso, o conceito aparece como **lacuna não confirmada** (hachurado no mapa).
8. **Lacuna raiz.** É uma lacuna sem nenhum pré-requisito, direto ou indireto, também com lacuna. A recomendação é "Revisar {conceito}", com a lista do que isso destrava.
9. **Estado derivado das respostas.** O banco guarda só as respostas; crença, estado e trilha são recalculados a cada consulta.

---

## API

A documentação interativa fica em http://localhost:8000/docs.

| Método | Rota | Retorno |
|---|---|---|
| GET | `/api/conceitos` | Conceitos com pré-requisitos, em ordem topológica. |
| POST | `/api/sessoes` `{nome}` | `{sessao_id, aluno_id}`. Cria o aluno se o nome ainda não existir, sem diferenciar maiúsculas. |
| GET | `/api/sessoes/{id}/proximo` | Item **sem** a resposta correta, o conceito em teste e o ganho; ou `{"fim": true}`. |
| POST | `/api/sessoes/{id}/respostas` `{item_id, opcao}` | `{acertou, correta, explicacao, estado}`. Item repetido ou sessão encerrada: 409. |
| GET | `/api/sessoes/{id}/diagnostico` | Diagnóstico, estado, trilha de raciocínio e limiares. |
| GET | `/api/turma/mapa` | `{conceitos, alunos: [{id, nome, estado, classificacao}], criticos, limiares}`, usando a última sessão de cada aluno. |
| GET | `/api/turma/risco` | Alunos com lacuna raiz, do que tem mais lacunas para o que tem menos. |
| GET | `/api/alunos/{id}` | Dados do aluno e diagnóstico da última sessão. |

---

## Decisões de projeto

Estas decisões foram tomadas ao longo do desenvolvimento, com base nos resultados da validação.

1. **Inferência sobre os estados viáveis do grafo**, em vez de tratar os conceitos como independentes. Com conceitos independentes, a seleção adaptativa e a aleatória quase empatavam (42,7% contra 37,0% de acerto), e um único erro já classificava o conceito.
2. **Ganho de informação sobre todos os conceitos**, e não só sobre os do item, porque pelo grafo uma resposta também informa sobre pré-requisitos e dependentes.
3. **Priori como rede bayesiana.** A alternativa (produto de 0,6 restrito aos estados viáveis) deixava os conceitos da base impossíveis de diagnosticar: variável começava em p = 1,00.
4. **Lacuna só depois de dois erros**, com a classe `nao_confirmada`.
   - A seleção adaptativa volta ao conceito para confirmar; a aleatória continua puramente aleatória, como linha de base.
   - Efeito na validação: lacuna falsa de 65% para 20%, acerto de 53,7% para 53,3% e inconclusivo de 11% para 25%.
5. **Lacuna raiz** considera pré-requisitos diretos e indiretos.
6. **Validação** inclui 60 alunos sem lacuna por configuração, para medir lacunas falsas.
7. **Turma de demonstração.** Os exemplos Ana (lacuna em escopo) e Bruno (lacuna em laço aninhado) respondem sem chute nem deslize, para a demonstração ser reproduzível. Os outros 28 alunos usam o ruído do modelo.
8. **Testes da API** usam a camada de serviço com um banco temporário, para não depender do `httpx`.

---

## Revisão pedagógica pendente

Os 45 gabaritos foram conferidos executando o código de cada questão. Ainda falta a revisão de uma pessoa da área:

| Item | Ponto a revisar |
|---|---|
| q04 | Marcado só como "tipos", mas usa o operador `+` (concatenação). |
| q11 | `input()` devolve texto: está marcado como entrada e saída + variável, mas a confusão é de tipos. |
| q19 | É uma pegadinha (`range(0)` não executa nada); confirmar se o nível é adequado. |
| q25 | Achar o maior valor conta como "busca em vetor"? |
| q42, q43 | Recursão "pura", mas os dois dependem de condicional (caso base). |
| q16, q18, q19, q31 | O enunciado pede uma contagem; conferir se fica claro para o aluno. |
| Todos | As descrições dos 15 conceitos em `dados/conceitos.json`. |

**Grafo:** Tipos de dados e Entrada e saída não são pré-requisito de nenhum outro conceito. Por isso a seleção adaptativa quase não os testa, e o acerto nesses dois conceitos é 0%. Se fizer sentido pedagogicamente ligá-los a outros conceitos (por exemplo, tipos → operadores), basta editar `dados/conceitos.json` e rodar a validação de novo.
