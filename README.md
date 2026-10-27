# Mapa de Lacunas Conceituais

**Qual conceito de programação o aluno ainda não entendeu?**

Em disciplinas como Algoritmos e Programação I, a nota diz *quanto* o aluno errou, mas não *qual conceito* ficou para trás. Dois alunos com nota 5,0 podem ter dificuldades completamente diferentes: um não entende escopo de variável, o outro não entende laços aninhados.

Este protótipo trata cada questão como um teste de conceitos específicos e usa o **padrão de erros**, seguindo um **grafo de pré-requisitos** entre os conceitos, para apontar **qual conceito está com lacuna** e o que revisar primeiro.

Ele foi desenvolvido como protótipo acadêmico para o **4º UMC Summit de Pesquisa, Inovação e Extensão** (categoria Inovação), em novembro de 2026.

## Destaques

- **Explicável:** cada questão vem com uma *trilha de raciocínio*, que mostra por que foi escolhida e como a estimativa de cada conceito mudou com a resposta.
- **Adaptativo:** a próxima questão é a que mais ajuda a esclarecer onde está a dificuldade.
- **Sem IA generativa e sem nenhuma API externa:** o motor é determinístico, baseado em modelos clássicos de diagnóstico cognitivo.
- **Duas telas:**
  - o **aluno** responde de 6 a 15 questões curtas e recebe o diagnóstico;
  - o **professor** vê o mapa de calor da turma, os conceitos mais críticos e os alunos em risco.
- **Leve e local:** Python, FastAPI, SQLite e HTML/CSS/JavaScript puro. Não precisa de Docker, nuvem nem cadastro.

---

## Como rodar na sua máquina

### 1. Pré-requisitos

- **Python 3.11 ou mais recente.** Baixe em [python.org/downloads](https://www.python.org/downloads/).
  - No Windows, marque **"Add python.exe to PATH"** durante a instalação.
  - Para conferir, rode `python --version` (ou `python3 --version` no Linux/macOS).
- **Git**, para clonar o repositório. Se preferir não usar o Git, baixe o ZIP pelo botão **Code → Download ZIP** desta página.

### 2. Baixar o projeto

```bash
git clone https://github.com/gomesOG/mapa-lacunas.git
cd mapa-lacunas
```

### 3. Instalar e iniciar

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/criar_banco.py
python scripts/popular_turma.py
uvicorn app.main:app --reload
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/criar_banco.py
python scripts/popular_turma.py
uvicorn app.main:app --reload
```

O que cada passo faz:
1. cria um ambiente virtual Python isolado em `.venv`;
2. ativa esse ambiente;
3. instala as três dependências (`fastapi`, `uvicorn` e `pytest`);
4. cria o banco local `mapa.db` com os conceitos e as questões;
5. cria uma turma de demonstração com 30 alunos simulados (opcional, mas deixa a tela do professor preenchida);
6. inicia o servidor.

### 4. Abrir no navegador

| Endereço | O que é |
|---|---|
| http://localhost:8000 | Página inicial, para escolher entre aluno e professor |
| http://localhost:8000/aluno.html | Responder às questões e ver o próprio diagnóstico |
| http://localhost:8000/professor.html | Mapa de calor da turma e diagnóstico de cada aluno |
| http://localhost:8000/docs | Documentação interativa da API |

Para parar o servidor, pressione `Ctrl + C` no terminal. Para usar de novo depois, basta ativar o ambiente (passo 2 da lista) e rodar `uvicorn app.main:app --reload`.

### Problemas comuns

<details>
<summary><b>Windows: "python não é reconhecido" ou abre a Microsoft Store</b></summary>

O Python não está no PATH. Reinstale pelo [python.org](https://www.python.org/downloads/) marcando **"Add python.exe to PATH"** e abra um terminal novo. Outra opção é usar o lançador `py` no lugar de `python`, por exemplo `py -m venv .venv`.
</details>

<details>
<summary><b>Windows: o PowerShell bloqueia o <code>Activate.ps1</code></b></summary>

Dá para rodar tudo sem ativar o ambiente, chamando o Python do `.venv` diretamente:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/criar_banco.py
.venv\Scripts\python.exe scripts/popular_turma.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
</details>

<details>
<summary><b>A porta 8000 já está em uso</b></summary>

Use outra porta, por exemplo `uvicorn app.main:app --reload --port 8001`, e abra http://localhost:8001.
</details>

<details>
<summary><b>"Banco não encontrado"</b></summary>

Rode `python scripts/criar_banco.py` antes de iniciar o servidor.
</details>

### Outros comandos

| Comando | O que faz |
|---|---|
| `python scripts/criar_banco.py --zerar` | Apaga o banco inteiro e recria do zero. Sem `--zerar`, recarrega as questões e mantém os alunos. |
| `python scripts/popular_turma.py` | Recria a turma de demonstração. Só os alunos simulados são apagados; os reais continuam. |
| `python scripts/validar_motor.py` | Roda a validação com alunos simulados (cerca de 2 minutos) e gera `resultados/validacao.csv` e `resultados/resumo.md`. |
| `pytest` | Roda os testes automatizados. |

---

## Como usar

**Como aluno:**
1. Digite seu nome e clique em **Começar**. Não há senha nem cadastro.
2. Responda às questões. Cada uma traz um trecho curto de código Python e 4 opções, e depois de responder você vê a explicação.
3. Ao final, você recebe a lacuna principal com a recomendação do que revisar, o domínio estimado de cada conceito e a linha do tempo do raciocínio do sistema.

**Como professor:** a tela mostra um **mapa de calor**, com os conceitos nas linhas e os alunos nas colunas. Passe o mouse para ver os valores e clique em um aluno para abrir o diagnóstico completo dele. Ao lado ficam os conceitos com mais lacunas na turma e os alunos em risco.

---

## Como funciona

O diagnóstico combina três ideias clássicas da área de avaliação educacional:

1. **Grafo de pré-requisitos.** São 15 conceitos de programação (variável, condicional, laço, vetor, função, escopo, recursão…) ligados por pré-requisitos: é preciso dominar escopo para dominar recursão. Isso restringe os perfis possíveis de aluno a **345 estados de conhecimento coerentes**, de 32.768 combinações livres. A ideia vem da Teoria dos Espaços de Conhecimento.
2. **Modelo DINA.** O aluno só acerta "de verdade" uma questão se dominar **todos** os conceitos que ela exige. Fora isso, pode acertar por chute (25%) ou errar por deslize (10%). Cada resposta atualiza, pela regra de Bayes, a probabilidade de cada estado de conhecimento.
3. **Seleção adaptativa.** A próxima questão é a que traz o maior **ganho de informação esperado**. Quando um conceito parece ter lacuna, o sistema volta a ele para confirmar.

Regras que deixam o diagnóstico mais confiável:
- **Confirmação por dois erros:** uma lacuna só é declarada depois de dois erros em questões que exigem o conceito, porque um erro isolado pode ser só distração.
- **Lacuna raiz:** se um conceito e um pré-requisito dele estão com lacuna, a causa está no pré-requisito, e é ele que o sistema recomenda revisar.
- **Reproduzível:** o banco guarda só as respostas, e todo o diagnóstico é recalculado a partir delas.

O núcleo do motor fica em [`app/motor/`](app/motor/): são funções puras, sem banco e sem rede. Todas as constantes do modelo estão em [`app/config.py`](app/config.py).

---

## Resultados da validação

O motor foi validado com **alunos simulados** (`python scripts/validar_motor.py`). Cada um tem uma lacuna "plantada" em um conceito, e o teste mede se o sistema a encontra. São 300 alunos por configuração, mais 60 alunos sem nenhuma lacuna para medir alarmes falsos.

| Configuração | Acerto (lacuna certa em 1º lugar) | Questões (média) | Inconclusivo | Lacuna falsa¹ |
|---|---|---|---|---|
| **Adaptativa** (este sistema) | **53,3%** | 14,1 | 25,3% | 20,0% |
| Aleatória (linha de base) | 36,0% | 14,4 | 38,3% | 13,3% |
| Adaptativa, com alunos mais "ruidosos" que o modelo supõe | 44,7% | 13,9 | 25,7% | 30,0% |

¹ Percentual de alunos sem lacuna que receberam alguma lacuna no diagnóstico (menor é melhor).

Ao acaso, entre 15 conceitos, o acerto seria de 6,7%. A seleção adaptativa acerta **17 pontos a mais** que a ordem aleatória, com o mesmo número de questões. A terceira linha mostra que o sistema se mantém mesmo quando os alunos se comportam de forma diferente do que o modelo supõe.

**Limitações conhecidas:**
- Em 25% dos casos, 15 questões não bastam para confirmar a lacuna, e o diagnóstico sai "inconclusivo".
- Conceitos que não são pré-requisito de nenhum outro (Tipos de dados e Entrada e saída) quase não são testados pela seleção adaptativa. Hoje o sistema não os diagnostica bem.
- É um protótipo: as questões ainda passam por revisão pedagógica, e os resultados acima vêm de simulação, não de alunos reais.

---

## Estrutura do projeto

```
app/
  config.py         constantes do modelo e caminhos
  main.py           rotas da API (FastAPI) e arquivos estáticos
  db.py             conexão SQLite e schema
  repositorio.py    consultas SQL
  servico.py        junta o banco e o motor
  motor/            núcleo do diagnóstico (funções puras)
  simulacao/        alunos simulados e experimento de validação
dados/              conceitos.json (15 conceitos) e itens.json (45 questões)
static/             telas: index.html, aluno.html, professor.html, css/, js/
scripts/            criar_banco.py, popular_turma.py, validar_motor.py
tests/              testes automatizados (pytest)
docs/               detalhes técnicos
```

Para a API, as decisões de projeto e a revisão pedagógica pendente, veja [`docs/DETALHES_TECNICOS.md`](docs/DETALHES_TECNICOS.md).

---

## Referências

- Junker, B. W.; Sijtsma, K. (2001). *Cognitive assessment models with few assumptions, and connections with nonparametric item response theory.* Applied Psychological Measurement, 25(3). (modelo DINA)
- Doignon, J.-P.; Falmagne, J.-C. (1999). *Knowledge Spaces.* Springer. (Teoria dos Espaços de Conhecimento)
- Leighton, J. P.; Gierl, M. J.; Hunka, S. M. (2004). *The attribute hierarchy method for cognitive assessment: a variation on Tatsuoka's rule-space approach.* Journal of Educational Measurement, 41(3).
- Corbett, A. T.; Anderson, J. R. (1995). *Knowledge tracing: Modeling the acquisition of procedural knowledge.* User Modeling and User-Adapted Interaction, 4.

---

## Licença

Distribuído sob a licença MIT: você pode usar, copiar, modificar e redistribuir, desde que mantenha o aviso de copyright. Veja [`LICENSE`](LICENSE).
