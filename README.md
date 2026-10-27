# Mapa de Lacunas Conceituais

Protótipo acadêmico apresentado no **4º UMC Summit de Pesquisa, Inovação e Extensão** (categoria Inovação), em 05/11/2026.

Em Algoritmos e Programação I, a nota diz *quanto* o aluno errou, mas não *qual conceito* ele não entendeu. Este sistema trata cada questão como um teste de conceitos específicos e usa o padrão de erros, seguindo um **grafo de pré-requisitos**, para inferir **qual conceito está com lacuna**.

- Motor determinístico e explicável: **sem IA generativa e sem nenhuma API externa**.
- Roda só localmente: Python + FastAPI + SQLite + HTML/CSS/JavaScript puro.
- Toda resposta gera uma **trilha de raciocínio**, que mostra por que cada questão foi escolhida e como cada estimativa mudou.

---

## Como rodar

Requisito: **Python 3.11 ou mais recente** (testado com 3.14).

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/criar_banco.py
python scripts/popular_turma.py
uvicorn app.main:app --reload
```

Se o PowerShell recusar o `Activate.ps1` por política de execução, dá para rodar sem ativar o ambiente, chamando o Python do `.venv` diretamente:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/criar_banco.py
.venv\Scripts\python.exe scripts/popular_turma.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/criar_banco.py
python scripts/popular_turma.py
uvicorn app.main:app --reload
```

Depois, abra **http://localhost:8000**. A documentação interativa da API fica em http://localhost:8000/docs.

| Comando | O que faz |
|---|---|
| `python scripts/criar_banco.py` | Cria o banco `mapa.db` e carrega `dados/conceitos.json` e `dados/itens.json`. Rodar de novo recarrega o conteúdo e **mantém** alunos e respostas. |
| `python scripts/criar_banco.py --zerar` | Apaga o banco inteiro e recria. |
| `python scripts/popular_turma.py` | Cria 30 alunos simulados com sessões completas (para o mapa de calor). Rodar de novo apaga e recria **só** os simulados. |
| `python scripts/validar_motor.py` | Roda a validação com alunos simulados e gera `resultados/validacao.csv` e `resultados/resumo.md` (cerca de 2 minutos). |
| `pytest` | Roda os testes (135). |

---

## Como o motor funciona

Todo o motor fica em `app/motor/`, que é **puro**: funções sem banco, sem arquivo e sem rede, que recebem dados e devolvem dados. As constantes ficam todas em `app/config.py`.

1. **Grafo de pré-requisitos** (`grafo.py`). São 15 conceitos num grafo acíclico (DAG); a aresta A → B significa "A é pré-requisito de B". A carga recusa ciclos e pré-requisitos inexistentes.
2. **Estados de conhecimento viáveis** (`modelo.py`). Um estado é o conjunto de conceitos que o aluno domina. Só valem os estados fechados por pré-requisito: quem domina recursão domina escopo. No grafo do projeto são **345 estados**, contra 32.768 combinações livres. A ideia vem da Teoria dos Espaços de Conhecimento.
3. **Crença inicial em rede bayesiana.** `PRIORI = 0,60` é a chance de dominar um conceito **dado que domina seus pré-requisitos**. Por isso a estimativa inicial cai com a profundidade no grafo: variável começa em 0,60 e recursão em 0,02.
4. **Modelo de resposta DINA.** O aluno só acerta "de verdade" se dominar **todos** os conceitos do item. Fora isso, acerta por chute (`CHUTE = 0,25`) ou erra por deslize (`DESLIZE = 0,10`). Cada resposta atualiza a crença pela regra de Bayes. A estimativa exibida, p, é a soma das probabilidades dos estados que contêm o conceito.
5. **Escolha da próxima questão** (`selecao.py` e `diagnostico.escolher_proxima`).
   - Normalmente vem o item com maior **ganho de informação esperado**, isto é, a queda esperada na soma das entropias de **todos** os conceitos. Como o grafo amarra os conceitos, uma resposta também informa sobre pré-requisitos e dependentes. Em empate, vence o item com menos conceitos e depois o menor id.
   - **Confirmação:** se um conceito está com p de lacuna e já tem um erro, a próxima questão é a de maior ganho entre as que testam diretamente esse conceito.
6. **Parada** (`diagnostico.py`). A sessão para em 15 questões, ou a partir de 6 se nenhuma questão traz ganho maior que 0,01 bit ou se todos os conceitos estão classificados. Uma lacuna ainda não confirmada conta como não classificada, então a sessão continua para confirmá-la.
7. **Classificação:**
   - p ≥ 0,70 é **dominado**; p ≤ 0,30 é **lacuna**; o resto é **incerto**.
   - Um p baixo só conta como lacuna depois de **dois erros** (`ERROS_PARA_LACUNA = 2`) em questões que exigem o conceito, ou se ele depende de uma lacuna já confirmada (quem não domina variável não domina recursão). Um erro isolado pode ser só um deslize.
   - Antes disso, o conceito aparece como **lacuna não confirmada** (hachurado no mapa). Isso também vale para o p baixo que vem só da estimativa inicial, sem erro nenhum.
8. **Lacuna raiz.** É uma lacuna sem nenhum pré-requisito, direto ou indireto, também com lacuna. Se o pré-requisito também está com lacuna, a causa está mais embaixo e quem é reportado é ele. A recomendação é "Revisar {conceito}", com a lista do que isso destrava.
9. **O estado é derivado das respostas.** O banco guarda só as respostas; crença, estado e trilha são recalculados a cada consulta, o que torna tudo reproduzível.

---

## Validação com alunos simulados

`python scripts/validar_motor.py`. Por configuração, são 300 alunos com uma lacuna plantada (20 por conceito). A lacuna e todos os conceitos que dependem dela ficam sem domínio. Há ainda **60 alunos que dominam tudo**, para medir lacunas falsas. A semente é fixa (42).

| Config | Seleção | Ruído do simulador | Acerto top-1 | Acerto top-2 | Questões (média) | Inconclusivo | Lacuna falsa¹ |
|---|---|---|---|---|---|---|---|
| A | adaptativa | igual ao motor (s = 0,10; g = 0,25) | **53,3%** | 55,7% | 14,1 | 25,3% | **20,0%** |
| B | aleatória | igual ao motor | 36,0% | 36,7% | 14,4 | 38,3% | 13,3% |
| C | adaptativa | **diferente** do motor (s = 0,15; g = 0,30) | 44,7% | 46,7% | 13,9 | 25,7% | 30,0% |

¹ Percentual dos alunos sem lacuna que saíram com alguma lacuna raiz apontada (menor é melhor).

- **Acerto top-1:** a lacuna plantada é a primeira lacuna raiz do diagnóstico. Ao acaso entre 15 conceitos, seria 6,7%.
- **A x B:** a seleção adaptativa acerta 17 pontos a mais que a aleatória (53,3% contra 36,0%), com um pouco menos de questões.
- **C** existe por honestidade metodológica. Se o simulador fosse idêntico ao modelo, o teste seria circular. Mesmo com o aluno mais ruidoso que o modelo supõe, o top-1 fica em 44,7%.
- **Lacuna falsa:** 20% dos alunos que dominam tudo saem com alguma lacuna apontada (configuração A).
- O detalhe por conceito está em `resultados/resumo.md`.

**Efeito da regra dos dois erros** (configuração A, antes → depois): lacuna falsa de 65% para 20%, top-1 de 53,7% para 53,3%, inconclusivo de 11% para 25%. O motor passou a apontar menos lacunas erradas e, em troca, diz "inconclusivo" com mais frequência quando não consegue confirmar a lacuna em 15 questões.

### Limitações conhecidas (para a banca e para a equipe)

- **Mais diagnósticos inconclusivos.** Em 25% dos alunos com lacuna, as 15 questões não bastam para chegar a dois erros no conceito certo. Nesses casos, o conceito aparece como "lacuna não confirmada", e não como lacuna.
- **Conceitos sem dependentes são pouco testados.** Tipos de dados e Entrada e saída não são pré-requisito de nenhum outro conceito. Testá-los informa só sobre eles, então o ganho de informação prefere outros itens. Na configuração A, o acerto top-1 nesses dois conceitos é 0%. Busca em vetor (10%) sofre do mesmo jeito.
- **Estimativa inicial pessimista no topo do grafo.** Um aluno forte precisa "provar" que domina os conceitos avançados. O que não foi testado aparece como "não confirmada", não como dominado.
- **"Conceitos mais críticos" conta lacunas herdadas.** Uma lacuna confirmada em qualquer pré-requisito de recursão também conta como lacuna em recursão. Por isso recursão tende a aparecer no topo da lista.

Caminhos possíveis, **não aplicados** para não ajustar parâmetros pelo resultado:
- incluir no ganho um termo para conceitos ainda não testados;
- ligar Tipos de dados e Entrada e saída a outros conceitos no grafo, se a equipe entender que são pré-requisitos;
- revisar `MAX_QUESTOES`.

---

## Telas

- **`/` (início):** escolha entre aluno e professor.
- **`/aluno.html`:**
  - O aluno digita o nome e responde de 6 a 15 questões, com a etiqueta "Em teste: {conceito}", o código, 4 opções e a explicação depois de responder.
  - No fim aparecem as lacunas raiz com a recomendação, as barras de domínio por conceito e a **linha do tempo do raciocínio**. "Pelo grafo" mostra os conceitos que mudaram por serem pré-requisitos ou dependentes.
- **`/professor.html`:**
  - Mapa de calor (conceitos × alunos, em CSS Grid), com o valor ao passar o mouse e a legenda de cores.
  - Ao lado, os conceitos mais críticos e os alunos em risco.
  - Clicar numa coluna abre o diagnóstico e a trilha do aluno. Nos simulados, aparece também a lacuna plantada.

### Turma de demonstração (`popular_turma.py`)

- 30 alunos simulados, com lacunas concentradas em **escopo** e **laço aninhado** e 4 alunos sem lacuna.
- **Ana** (lacuna em escopo) e **Bruno** (lacuna em laço aninhado) são os exemplos do slide 5. Eles respondem **sem chute nem deslize**, para a história do slide ser reproduzível, e o motor diagnostica os dois corretamente.
- Os demais usam o ruído do modelo. O diagnóstico bate com a lacuna plantada em 17 dos 30 alunos, coerente com a validação.

---

## API

| Método | Rota | Retorno |
|---|---|---|
| GET | `/api/conceitos` | Conceitos com pré-requisitos, em ordem topológica. |
| POST | `/api/sessoes` `{nome}` | `{sessao_id, aluno_id}`. Cria o aluno se o nome ainda não existir, sem diferenciar maiúsculas. |
| GET | `/api/sessoes/{id}/proximo` | Item **sem** `correta`, o conceito em teste e o ganho; ou `{"fim": true}`. |
| POST | `/api/sessoes/{id}/respostas` `{item_id, opcao}` | `{acertou, correta, explicacao, estado}`. Item repetido ou sessão encerrada: 409. |
| GET | `/api/sessoes/{id}/diagnostico` | Diagnóstico, estado, trilha de raciocínio e limiares. |
| GET | `/api/turma/mapa` | `{conceitos, alunos: [{id, nome, estado, classificacao}], criticos, limiares}`, usando a última sessão de cada aluno. |
| GET | `/api/turma/risco` | Alunos com lacuna raiz, do que tem mais lacunas para o que tem menos. |
| GET | `/api/alunos/{id}` | Dados do aluno e diagnóstico da última sessão. |

---

## Estrutura

```
app/
  config.py            constantes do modelo e caminhos
  main.py              rotas FastAPI + arquivos estáticos
  db.py                conexão SQLite e schema
  repositorio.py       única camada que fala SQL
  servico.py           junta repositório e motor
  motor/               PURO: grafo.py, modelo.py, selecao.py, diagnostico.py
  simulacao/           gerador.py (alunos simulados), experimento.py
dados/                 conceitos.json (15), itens.json (45)
static/                index.html, aluno.html, professor.html, css/, js/
scripts/               criar_banco.py, popular_turma.py, validar_motor.py
tests/                 pytest
```

---

## Decisões que divergem da especificação original

Todas foram aprovadas pela equipe durante o desenvolvimento.

1. **Inferência sobre os estados viáveis do grafo** em vez de conceitos independentes (seção 6.3). Com conceitos independentes, a seleção adaptativa e a aleatória quase empatavam (42,7% contra 37,0% de top-1), e um único erro já classificava o conceito.
2. **Ganho de informação sobre todos os conceitos** (seção 6.4), e não só sobre os do item.
3. **`PRIORI` reinterpretado** como "chance de dominar dado que domina os pré-requisitos". A outra forma (produto de 0,6 restrito aos estados viáveis) deixava os conceitos da base praticamente impossíveis de diagnosticar: variável começava em p = 1,00.
4. **Lacuna só depois de dois erros** em questões que exigem o conceito (ou herdada de um pré-requisito confirmado), com a classe nova `nao_confirmada`.
   - A política adaptativa volta ao conceito para confirmar a lacuna. A seleção aleatória (B) continua puramente aleatória, como linha de base.
   - `sem_lacunas` exige todos os conceitos dominados; caso contrário, sem lacuna, o diagnóstico é `inconclusivo`.
   - Uma versão anterior exigia só "evidência" (alguma questão sobre o conceito). Ela limpava o mapa, mas não mudava a taxa de lacuna falsa (65%), porque as lacunas falsas vinham de deslizes isolados.
5. **Lacuna raiz** considera pré-requisitos diretos **e indiretos**.
6. **`reproduzir(respostas, itens, espaco)`** recebe `[(item_id, acertou), ...]`, porque a trilha precisa do id do item e do motivo da escolha.
7. **Recomendação** lista como "destravar" só os descendentes que ainda não estão dominados.
8. **Validação** inclui 60 alunos sem lacuna por configuração, para medir lacunas falsas.
9. **Arquivos extras:**
   - `pytest.ini`, para o `pytest` achar o pacote `app`;
   - `tests/conftest.py`, `tests/test_itens.py` e `tests/test_servico.py`;
   - `static/js/componentes.js`, com as peças de tela compartilhadas.
   - Os testes da API usam a camada de serviço, porque o `TestClient` do FastAPI exige o `httpx`, que está fora das dependências permitidas.

---

## Revisão pedagógica pendente

Os 45 gabaritos foram conferidos **executando o código** de cada item. O que ainda precisa de uma pessoa da equipe:

| Item | Ponto a revisar |
|---|---|
| q04 | Marcado só como "tipos", mas usa o operador `+` (concatenação). |
| q11 | `input()` devolve texto: está marcado como entrada e saída + variável, mas a confusão é de tipos. |
| q19 | É uma pegadinha (`range(0)` não executa nada); confirmar se o nível é adequado. |
| q25 | Achar o maior valor conta como "busca em vetor"? |
| q42, q43 | Recursão "pura", mas os dois dependem de condicional (caso base). |
| q16, q18, q19, q31 | O enunciado pede uma contagem (quantas vezes / quantas linhas); conferir se fica claro para o aluno. |
| Todos | As **descrições dos 15 conceitos** em `dados/conceitos.json` foram escritas no desenvolvimento e não passaram por revisão. |

Além disso, **Tipos de dados** e **Entrada e saída** não são pré-requisito de nenhum outro conceito no grafo. Se a equipe entender que são (por exemplo, tipos → operadores), vale atualizar `conceitos.json`; isso também melhora o diagnóstico desses conceitos.

---

## Referências

- **Modelo DINA:** Junker, B. W.; Sijtsma, K. (2001). *Cognitive assessment models with few assumptions, and connections with nonparametric item response theory.* Applied Psychological Measurement, 25(3).
- **Knowledge Tracing:** Corbett, A. T.; Anderson, J. R. (1995). *Knowledge tracing: Modeling the acquisition of procedural knowledge.* User Modeling and User-Adapted Interaction, 4.
- **Teoria dos Espaços de Conhecimento** (grafo de pré-requisitos e estados viáveis): Doignon, J.-P.; Falmagne, J.-C. (1999). *Knowledge Spaces.* Springer.
- **Hierarquia de atributos em diagnóstico cognitivo** (trabalho relacionado à restrição dos estados pelo grafo): Leighton, J. P.; Gierl, M. J.; Hunka, S. M. (2004). *The attribute hierarchy method for cognitive assessment: a variation on Tatsuoka's rule-space approach.* Journal of Educational Measurement, 41(3).
