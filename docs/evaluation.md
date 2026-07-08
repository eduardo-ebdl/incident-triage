# Manual evaluation plan

Stage 1 intentionally avoids automated LLM tests: local tests must run without network access
or API keys. This document is a lightweight manual evaluation checklist for the synthetic
incidents.

Run:

```bash
python scripts/run_digest.py --window "90 day"
```

Then compare the model output against the expected triage below.

| Error pattern | Expected category | Expected severity | Expected action | Notes |
| --- | --- | --- | --- | --- |
| `ZeroDivisionError` | `code` | `medium` | `fix` | Recurrent deterministic code bug. |
| `KeyError` | `data` | `medium` | `fix` | Missing field or schema drift in the input record. |
| `ImportError` / `ModuleNotFoundError` | `dependency` | `high` | `fix` | Runtime dependency is missing. |
| `TypeError` | `code` | `medium` | `fix` | Incompatible types in application logic. |
| `FileNotFoundError` | `config` | `high` | `fix` | Missing input path, mount, or configured file. |
| `IndexError` | `code` | `medium` | `fix` | Code assumes a list has more items than it does. |
| `AttributeError` on `NoneType` | `data` | `medium` | `fix` | Null value reached code that expects a string/object. |
| `NameError` | `code` | `medium` | `fix` | Undefined variable in job code. |
| `AssertionError` on row count | `data` | `high` | `fix` | Data quality expectation failed. |
| `ValueError` parsing `N/A` | `data` | `medium` | `fix` | Invalid value for numeric conversion. |
| Spark timeout / OOM | `resource` | `high` | `escalate` | Large join likely needs Spark tuning or query redesign. |

Suggested pass criteria:

- The model picks the expected category or a defensible adjacent category.
- Severity is within one level of the expected severity unless the trace clearly justifies a
  stronger call.
- The recommended action is operationally useful and grounded in the traceback.
- Root cause does not invent evidence that is not present in `error_message` or `error_trace`.
- Deduplication is visible: the repeated `ZeroDivisionError` appears once with two occurrences.
