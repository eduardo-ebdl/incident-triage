# CLAUDE.md — Incident Triage Copilot

Contexto e comportamento para trabalho neste diretório.

## Sobre o projeto

- Projeto de portfólio **em dupla** com um Data Engineer (DE). Databricks (Delta, Vector Search, Workflows).
- Fonte de verdade da spec/plano: `wolfs-den/projects/_ideas/incident-triage-copilot.md` (no vault privado, fora deste repo).
- **Lado do DE (feito):** 10 fake jobs que falham (um por tipo de exceção Python) + ingestão que grava os erros em uma Delta table.
- **Lado AI/ML (este repo, meu foco):** ler a tabela, agente que classifica/triagem os erros e manda um digest.
- **Repo principal ficará no GitHub do DE** — este diretório local é onde eu (Eduardo) desenvolvo o lado de IA antes de portar/PR para o repo dele. Depois faço fork para o próprio GitHub.
- Dados sintéticos apenas. Nunca dados reais da Indicium.

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
| error_trace | string — **input-chave da IA** |
| run_page_url | string |
| trigger | string |

Não existe `task_run_id` na tabela — não é bloqueio (jobs são single-task; `run_id` já identifica a execução).

## Estágio 1 (MVP digest) — ordem de execução

P1 ler tabela → P2 schema Pydantic `TriageResult` → P3 dedup por hash do `error_message` → P4 1 chamada
Claude Haiku 4.5 por incidente (structured output/tool-calling) → P5 agregar por job/severidade →
P6 email SMTP → P7 MLflow Tracing ligado desde o P4.

Não forçar RAG/ReAct neste estágio — isso é Estágio 2 (Vector Search + LangGraph, depois que P1-P7
rodar estável contra a tabela real).

## Ambiente

- Sem acesso direto ao workspace Databricks a partir desta máquina ainda. `read_incidents.py` suporta
  dois modos: `databricks` (via `databricks-sql-connector`, precisa de `DATABRICKS_SERVER_HOSTNAME`,
  `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN` no `.env`) e `mock` (lê `tests/fixtures/mock_incidents.csv`,
  usado para dev/teste local sem depender do workspace).
- LLM: Anthropic API direto, `claude-haiku-4-5` em dev (custo baixo). Trocar para Sonnet/Opus só na
  execução "de verdade", via config, não via mudança de código.
- Precisa de `ANTHROPIC_API_KEY` no `.env` para P4 rodar de verdade (sem ela, só dá pra testar o resto
  do pipeline com o LLM mockado).

## Como trabalhar

- Idioma: pt-BR nas respostas e nos comentários/commits.
- Trabalhar direto em `main` por enquanto (repo local ainda não tem remoto do DE definido).
- Testes cobrindo dedup e schema não devem depender de rede/API key — só a chamada real ao Claude
  (P4) é que é "integration", roda separada.
