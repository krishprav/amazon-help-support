# AmazonHelp support agent

An offline support-agent experiment with a fixed real-data subsample, two baselines, traceable reply evidence and a blind human-review workflow. Python 3.10+; no third-party packages.

The reported system is the offline agent. Reviewers can reproduce the cached headline results in under 15 minutes without Kaggle, an API key, or the full dataset. That 15-minute claim excludes the original dataset download, human annotation time, and any uncached judge API calls.

## Quick start (under 15 minutes, offline)

Run from the repository root. Use `python3` if `python` is not on your PATH.

```bash
python3 -m unittest discover -s tests -v
python3 src/workflow.py ask "My parcel is marked delivered but I cannot find it."
python3 src/audit.py
```

To regenerate all 600 outputs (three systems × 200 real messages):

```bash
python3 src/workflow.py generate
```

The included `results/predictions.json` is a runtime cache, not a quality claim. Regeneration should match replies, intents, routing and citations; latency fields may differ.

After gold labels, ratings and a cached judge run are in the repo:

```bash
python3 src/replay.py
python3 src/workflow.py agreement
python3 src/report.py
python3 src/workflow.py check
```

`workflow.py check` recomputes metrics and agreement and refuses stale or incomplete artifacts.

## Human evaluation

Labels must be supplied by a named person. The software does not generate gold labels. Two equivalent paths:

**CLI (resumable, saves after every row):**

```bash
python3 src/annotate.py gold --name YOUR_NAME
python3 src/annotate.py rates --name YOUR_NAME
python3 src/annotate.py status
```

Complete gold before ratings. The rater CLI never opens `review/review_mapping.json` or judge scores.

**Workbook:**

`review/Hiver-human-review.xlsx` is blank. Fill **Gold labels** (200 rows) then **Reply ratings** (60 rows). Use the **Guide** and **Evidence** tabs. Do not inspect model identities first.

```bash
python3 src/workbook.py   # rebuild a blank workbook if needed
python3 src/import_review.py review/Hiver-human-review.xlsx
```

Import checks IDs, unchanged message/draft text, the Evidence tab, and evidence-ID association. Names are self-attestations.

Sampling and labelling rules: [docs/annotation.md](docs/annotation.md).

## LLM judge

The included judge is a Chat Completions HTTPS call. `.env.example` documents variables; the file is not autoloaded. Never commit keys. AgentRouter rejects the default Python User-Agent, so set `JUDGE_USER_AGENT`. Content-filter blocks on a quoted tweet retry `JUDGE_FALLBACK_MODELS` rather than inventing a score.

AgentRouter example:

```bash
export JUDGE_BASE_URL='https://agentrouter.org/v1'
export JUDGE_MODEL='deepseek-v4-flash'
export JUDGE_USER_AGENT='QwenCode/0.2.0 (linux; x64)'
read -s JUDGE_API_KEY
export JUDGE_API_KEY
python3 src/judge.py
```

Confirm the exact model id with your provider. The judge rates 60 anonymized replies with equal evidence packets, caches by rubric/case/endpoint/model, and resumes interruptions. HTTP 429 and 5xx get bounded retries. A content-filter block retries `JUDGE_FALLBACK_MODELS`. Schema-invalid output fails rather than becoming a score. Cached `results/judge.json` is enough for the 15-minute replay; uncached cost and latency depend on the provider. `workflow.py check` stays red until that file is complete.

Optional LLM drafting (`python3 src/workflow.py generate --llm --output results/llm_predictions.json`) is a side experiment. It is not the reported system and would need a new blind cohort.

## Design

| System | Intent | Reply | Routing |
|---|---|---|---|
| Trivial | Weak-training majority | Generic acknowledgement | Always escalate |
| Simple | Ordered keyword rules | Nearest historical reply | Always escalate |
| Agent | Explicit-action rules, with TF-IDF voting for unmatched messages | Source-checked training question or topic-specific fallback | Auto-handle only whole-message social acknowledgements |

Evidence is drawn only from the training partition. Source-span checks prove where a quoted question came from; they do not prove it is relevant. Account actions and current-policy decisions go to human review.

## Report and decision log

[Report](docs/report.md) · [Decision log](docs/decision-log.md) · [Annotation protocol](docs/annotation.md)

Headline numbers without human gold are operational (600 predictions, 0/200 auto-handles), not quality scores. Escalating every message can look like perfect safety while automating nothing.

## Data provenance and rebuilding

Source: [Stuart Axelbrooke / thoughtvector, Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter). CC BY-NC-SA 4.0; see `DATA_LICENSE.md`. This package is a redacted 2,280-message subsample. Redaction is best-effort.

`data/cohort.json` pins tweet IDs. To rebuild from your own `twcs.csv`:

```bash
python3 src/support.py prepare --input /absolute/path/to/twcs.csv --brand AmazonHelp --out data
```

That writes blank train/dev/test labels. Completed gold lives in `data/gold.csv`. Reply outcomes are not independently verified resolutions.

## Repository map

- `src/support.py`: importer, cleaning, retrieval and agent
- `src/workflow.py`: generation, scoring and evidence-chain checks
- `src/evaluation.py`: metrics, bootstrap, Wilson intervals, rating agreement
- `src/judge.py`: blind cached LLM judge
- `src/workbook.py`, `src/import_review.py`, `src/annotate.py`: review artifacts
- `src/report.py`, `src/audit.py`, `src/replay.py`: report, audit and replay
- `tests/`: leakage, redaction, catalog fail-closed, metric denominators, review import

## What’s in the repo

Gold labels, blind ratings, cached predictions, and scored metrics are included. `.env`, API keys, `results/judge_cache/`, and the original `twcs.csv` are not.

`results/judge.json` is not here. A live judge run scored 3 of 60 replies, then the provider returned HTTP 405; the rest were not invented. `python3 src/workflow.py check` stays red until a complete judge file exists.

## Attribution

Application code, tests and documents were written with an AI coding assistant. No third-party application code was copied. TF-IDF cosine retrieval and the metric formulas are standard methods. Metric definitions were checked against the scikit-learn documentation linked in the report.
