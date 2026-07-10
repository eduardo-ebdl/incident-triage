# CLAUDE.md — Incident Triage Copilot

Contexto e comportamento para trabalho neste diretório.

## Sobre o projeto

- Projeto de portfólio **em dupla** com um Data Engineer (DE). Databricks (Delta, Vector Search, Workflows).
- Fonte de verdade da spec/plano completo: `wolfs-den/projects/_ideas/incident-triage-copilot.md` (no vault
  privado, fora deste repo) — ler lá antes de planejar o Estágio 2.
- **Lado do DE (feito):** 10 fake jobs que falham (um por tipo de exceção Python) + ingestão que grava os
  erros em uma Delta table.
- **Lado AI/ML (este repo, meu foco):** ler a tabela, agente que classifica/triagem os erros e manda um digest.
- **Repo:** `https://github.com/eduardo-ebdl/incident-triage`, branch `main`. Trabalhar direto em `main`
  (sem PR/branch por enquanto).
- Dados sintéticos apenas. Nunca dados reais da Indicium.

## Status — Estágio 1 (MVP digest): CONCLUÍDO e verificado contra dado real

P1 ler tabela → P2 schema Pydantic `TriageResult` → P3 dedup por hash do `error_message` → P4 1 chamada
Claude Haiku 4.5 por incidente (tool-calling forçado) → P5 agregar por job/severidade → P6 email SMTP →
P7 MLflow Tracing no P4. Os 7 passos foram rodados de ponta a ponta contra a tabela real (não só o mock)
e o email chegou formatado corretamente. Achado real no caminho: o próprio job de ingestão do DE
("Job Error Logger", job_id 465557843776121) falha com `[CANNOT_DETERMINE_TYPE]` — `createDataFrame()`
sem `schema` explícito quebra quando algum campo vem `None` — e grava a mesma falha 3x na tabela (bug de
duplicação na escrita). Reportado ao DE.

Não forçar RAG/ReAct — isso é Estágio 2 (Vector Search + LangGraph, planejado na spec no wolfs-den, ainda
iniciado pelo P8).

## Status — Estágio 2

P8 foi implementado e verificado no Databricks: 18 resoluções sintéticas, endpoint
`incident-triage-ai-search`. **Já está no destino de arquitetura definitivo:**
`observability.dev.resolution_memory` + índice `observability.dev.resolution_memory_index`
(movido do checkpoint provisório em `workspace.default` assim que o `CREATE TABLE` foi concedido —
confirmado com uma tabela de teste real, não só "achando" que tinha sido liberado). Índice
`ONLINE_NO_PENDING_UPDATE`, 18 linhas, busca híbrida re-verificada com o mesmo resultado de antes
(`spark-join-oom` em 1º, score `1.000`). O checkpoint antigo em `workspace.default` ficou obsoleto
(nada no repo aponta mais pra ele) e pode ser apagado.

**Retrieval plugado no P4 (não é o P9 ainda).** `triage_incident` agora chama
`search_past_resolutions(error_message)` antes de montar o prompt e passa até 3 casos recuperados pro
Claude, pedindo pra só preencher `suggested_fix`/`sources` quando um caso genuinamente se aplica (senão
deixar vazio — sem forçar match). Verificado contra dado real: 9 dos 11 incidentes vieram com fix
fundamentado e fonte citada; os outros 2 (`AttributeError`, `AssertionError`) ficaram sem sugestão porque
nenhum dos 3 casos recuperados batia de verdade — o guardrail funcionou. `_retrieve_grounding` degrada
silenciosamente pra lista vazia se o Estágio 2 não estiver configurado (sem token, sem índice, sem rede),
então quem só tem o Estágio 1 rodando não quebra.

Isso ainda é uma chamada única com contexto injetado, não um agente. **P9 (LangGraph ReAct)** — onde o
agente decide ativamente quais tools chamar e investiga em loop — continua não iniciado. P10
(rerank/fusão) e P11 (guardrail formal de grounding, hoje é só instrução de prompt) também não.

### Preparação do P9 — colunas de metadata do run (10/07)

O DE adicionou 8 colunas novas na `job_error_logs`: `cluster_spec`, `spark_version`, `num_workers`,
`spark_conf`, `libraries`, `attempt_number`, `repair_history`, `task_run_id`. Verificado contra a API
real de Jobs (`/api/2.2/jobs/runs/get`) qual dessas vai dar certo:

- **Nunca vão vir preenchidas — os fake jobs rodam em compute serverless:** `cluster_spec`,
  `spark_conf`, `num_workers`, `spark_version`. Confirmado: a resposta real da API não tem
  `new_cluster`, `existing_cluster_id`, `cluster_instance` nem `spark_version` — só
  `"environment_key": "default"`. Não é bug de ingestão, é a natureza do serverless (sem cluster
  fixo pra descrever). **Não esperar essas 4 no design do P9** — o tool `get_run_metadata` não deve
  contar com elas. Não vale a pena pedir ao DE pra "corrigir"; não tem o que corrigir.
- **Deveriam vir preenchidas, mas ainda vêm NULL — gap real de ingestão:** `attempt_number`,
  `repair_history`. A API já devolve isso de bandeja (ex.: task repetida com `attempt_number: 0`
  depois `attempt_number: 1` no mesmo `run_id`, evidência de retry/repair) — só falta o código do
  DE extrair e gravar. Continua pendente do lado dele.
- **Descoberta nova, não pedida ainda:** a API também devolve `queue_duration` e, quando aplicável,
  `queue_reason` (ex.: `"Queued due to reaching maximum number of allowed active runs (5)"`) —
  sinal genuinamente útil em serverless (limite de concorrência), e não tem coluna nenhuma pra isso
  hoje. Vale adicionar aos pedidos pro DE quando for pedir `attempt_number`/`repair_history`.
- **Não apagar as 4 colunas serverless da tabela real.** O código de ingestão do DE provavelmente
  ainda as referencia num INSERT/MERGE; ficarem sempre `NULL` é inofensivo, mas um `ALTER TABLE DROP
  COLUMN` por fora pode quebrar o próximo run dele se ele não tiver alinhado a remoção antes.

## Status — Estágio 1.5

Concluído: README ampliado para portfólio, digest sanitizado em `docs/sample_digest.md`, plano de
avaliação manual em `docs/evaluation.md`, fallback por incidente quando Claude falha e preservação do
corpo do digest quando SMTP falha. `unknown` existe apenas como fallback interno e não é oferecido ao
LLM. Após o P8, a suíte local ficou com 13 testes passando.

## A "seam" — contrato de dados

Catálogo/schema/tabela confirmados: **`observability.dev.job_error_logs`**

| Coluna | Tipo |
|---|---|
| log_timestamp | timestamp |
| job_id | bigint |
| job_name | string |
| run_id | bigint |
| run_name | string |
| start_time | timestamp |
| end_time | timestamp |
| duration_seconds | bigint |
| result_state | string (FAILED / TIMEDOUT) |
| state_message | string |
| task_key | string |
| error_message | string |
| error_trace | string — **input-chave da IA**, real vem com códigos ANSI de cor (stripados no P1) |
| run_page_url | string |
| trigger | string |

Não existe `task_run_id` na tabela — não é bloqueio (jobs são single-task; `run_id` já identifica a execução).

Os fake jobs do DE foram semeados **uma vez** (19/06), não rodam diariamente — por isso `fetch_incidents`
aceita `window` (default `"1 day"`, mas pra ver os dados de teste hoje é preciso algo como `"90 day"`,
via `--window` no script ou `run_digest(window=...)`).

## Estrutura do código

```
src/incident_triage/
  schema.py     P2 — TriageResult, LLMTriage (Pydantic; inclui suggested_fix/sources do P8)
  incidents.py  P1 — fetch_incidents(); backend "databricks" (real) ou "mock" (CSV); strip de ANSI aqui
  dedup.py      P3 — hash do error_message, agrupa em IncidentGroup
  memory.py     P8 — ResolutionRecord/Match, load_resolution_seed, search_past_resolutions (AI Search)
  triage.py     P4 — retrieval (P8) + chamada Claude (tool-calling), + P7 (@mlflow.trace)
  aggregate.py  P5 — agrupa por job/severidade
  digest.py     P6 — formata texto (com suggested fix quando houver) + envia SMTP
  pipeline.py   orquestra P1→P7 (run_digest), fallback por incidente se o LLM falhar
scripts/run_digest.py            entrypoint CLI (--send, --window)
scripts/provision_ai_search.py   provisiona a Delta table + índice do P8 (idempotente)
scripts/search_resolution_memory.py   smoke test manual do retrieval
tests/          dedup, schema, memory, pipeline, triage — sem rede (mock ou fakes injetados)
```

## Ambiente

- **Backend de dados:** `INCIDENT_TRIAGE_BACKEND` no `.env` — `mock` (default, lê
  `tests/fixtures/mock_incidents.csv`, zero credencial) ou `databricks` (real, precisa de
  `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`). Hoje está configurado como
  `databricks` com acesso real ao workspace do DE.
- **LLM:** Anthropic API direto (`ANTHROPIC_API_KEY` no `.env`), `claude-haiku-4-5` em dev. Trocar pra
  Sonnet/Opus só na execução "de verdade", via `INCIDENT_TRIAGE_MODEL`, não via mudança de código.
- **Email:** `SMTP_*` + `DIGEST_TO_EMAIL` no `.env`. Hoje aponta pra uma conta descartável do
  [Ethereal Email](https://ethereal.email) (captura o email numa caixa web, não entrega de verdade —
  ótimo pra dev, a conta expira sozinha por inatividade).
- **Tracing:** `mlflow` é dependência opcional (`pip install -e ".[tracing]"`); sem ele, `@mlflow.trace`
  vira no-op silencioso (checar se está instalado antes de assumir que P7 está gerando traces!). Tracking
  store local por padrão (`mlflow.db`, sqlite — gitignored).
- **Instalação:** `pip install -e ".[dev,databricks,tracing]"` dentro do `.venv` já criado na raiz do repo.
- `.env` nunca vai pro git (está no `.gitignore`, junto com `.venv/`, `.idea/`, `mlflow.db`).

## Como trabalhar

- Idioma: pt-BR nas respostas e nos comentários/commits.
- Testes cobrindo dedup, schema e fallback do pipeline não devem depender de rede/API key — rodam só contra
  o mock. A chamada real ao Claude (P4) e a leitura real do Databricks são verificadas manualmente via
  `python scripts/run_digest.py`, não fazem parte do `pytest`.
- Antes de reportar um estágio como "concluído", rodar o checkpoint real (pipeline ponta a ponta contra
  dado real, não só o mock) — foi assim que se pegou o P7 rodando em no-op silencioso por falta do `mlflow`.

## Direção de produto / feedback

- Não reescrever o core do Estágio 1 sem necessidade: o recorte atual está bom e já fecha o fluxo
  operacional ponta a ponta.
- Próximo ganho principal é deixar o projeto mais demonstrável para portfólio: exemplo sanitizado de
  digest, seção de arquitetura mais clara, saída esperada e narrativa "entrada -> triagem -> digest".
- Adicionar uma avaliação pequena e manual antes de sofisticar a arquitetura: para os incidentes
  sintéticos, comparar classificação esperada vs. classificação do LLM e registrar acertos/discordâncias.
- Fortalecer robustez operacional: se uma chamada Claude falhar, o digest deveria poder sair com item de
  triagem indisponível; se SMTP falhar, o digest ainda deveria ser impresso/salvo.
- Usar o MLflow tracing como evidência do comportamento do sistema: registrar modelo, quantidade de
  incidentes, quantidade de grupos deduplicados e tempo total quando fizer sentido.
- Estágio 2 só deve trazer RAG/LangGraph quando houver contexto útil para recuperar: runbooks sintéticos,
  padrões conhecidos de exceção, histórico de incidentes ou documentação Databricks. Evitar "agent loop"
  sem ganho concreto para a triagem.
