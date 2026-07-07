# AGENTS.md — Incident Triage Copilot

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
não iniciado).

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
  schema.py     P2 — TriageResult, LLMTriage (Pydantic)
  incidents.py  P1 — fetch_incidents(); backend "databricks" (real) ou "mock" (CSV); strip de ANSI aqui
  dedup.py      P3 — hash do error_message, agrupa em IncidentGroup
  triage.py     P4 — chamada Claude (tool-calling), + P7 (@mlflow.trace, no-op se mlflow não instalado)
  aggregate.py  P5 — agrupa por job/severidade
  digest.py     P6 — formata texto + envia SMTP
  pipeline.py   orquestra P1→P7 (run_digest)
scripts/run_digest.py   entrypoint CLI (--send, --window)
tests/          dedup + schema, sem rede (rodam sempre contra o mock)
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
- Testes cobrindo dedup e schema não devem depender de rede/API key — rodam só contra o mock. A chamada
  real ao Claude (P4) e a leitura real do Databricks são verificadas manualmente via
  `python scripts/run_digest.py`, não fazem parte do `pytest`.
- Antes de reportar um estágio como "concluído", rodar o checkpoint real (pipeline ponta a ponta contra
  dado real, não só o mock) — foi assim que se pegou o P7 rodando em no-op silencioso por falta do `mlflow`.
