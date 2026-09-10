# AmazonHelp support agent

Offline experiment on AmazonHelp tweets: classify the request, draft a historically grounded reply, and decide whether a human should review it. Python 3.10+; standard library only.

The reported system is the offline agent. Cached predictions replay without Kaggle or an API key. That does not include the original dataset download, annotation time, or uncached judge calls.

## Quick start

```bash
python3 -m unittest discover -s tests -v
python3 src/workflow.py ask "My parcel is marked delivered but I cannot find it."
python3 src/audit.py
```

Regenerate all 600 outputs (three systems × 200 messages):

```bash
python3 src/workflow.py generate
```

`results/predictions.json` is a runtime cache, not a quality claim. Regeneration should match replies, intents, routing and citations; latency may differ.

Rescore from the packaged gold labels:

```bash
python3 src/replay.py
python3 src/report.py
```

`python3 src/workflow.py agreement` and `python3 src/workflow.py check` need a complete `results/judge.json`. That file is not packaged.

## Human evaluation

Gold labels and ratings must come from a named person. The software does not generate them.

```bash
python3 src/annotate.py gold --name YOUR_NAME
python3 src/annotate.py rates --name YOUR_NAME
python3 src/annotate.py status
```

Complete gold before ratings. The rater CLI never opens `review/review_mapping.json` or judge scores.

`review/human-review.xlsx` is a blank template generated **before** labelling. Do not run the generator on a filled workbook. To rebuild a blank copy:

```bash
python3 src/workbook.py --output /tmp/human-review.xlsx
```

The generator refuses to overwrite an existing file unless you pass `--force`. After filling Gold labels then Reply ratings, import:

```bash
python3 src/import_review.py path/to/filled.xlsx
```

Import checks IDs, unchanged message/draft text, the Evidence tab, and evidence-ID association. Names are self-attestations.

Protocol: [docs/annotation.md](docs/annotation.md).

## LLM judge

Chat Completions over HTTPS using Python’s standard library (`urllib`). `.env.example` documents variables and is not autoloaded. Never commit keys. The reported offline agent needs no `curl` and no API.

```bash
export JUDGE_BASE_URL='https://agentrouter.org/v1'
export JUDGE_MODEL='deepseek-v4-flash'
export JUDGE_USER_AGENT='QwenCode/0.2.0 (linux; x64)'
read -s JUDGE_API_KEY
export JUDGE_API_KEY
python3 src/judge.py
```

Some providers reject Python’s default User-Agent; set `JUDGE_USER_AGENT` as above. Content-filter blocks retry fallback models, then retry with historical tweet text omitted. HTTP 429 and 5xx get bounded retries. HTTP 405 means the provider blocked this client or network; scores are not invented. Invalid JSON is not turned into a score.

Optional LLM drafting (`python3 src/workflow.py generate --llm --output results/llm_predictions.json`) is a side experiment, not the reported system.

## Design

| System | Intent | Reply | Routing |
|---|---|---|---|
| Trivial | Weak-training majority | Generic acknowledgement | Always escalate |
| Simple | Ordered keyword rules | Nearest historical reply | Always escalate |
| Agent | Explicit-action rules, TF-IDF voting for unmatched messages | Source-checked training question or topic-specific fallback | Auto-handle only whole-message social acknowledgements |

Evidence comes only from the training partition. A source span shows where a quoted question came from; it does not prove the question is relevant.

## Report

[Report](docs/report.md) · [Decision log](docs/decision-log.md) · [Annotation protocol](docs/annotation.md)

Escalating every message can look like perfect safety while automating nothing. In this sample the agent auto-handles 0/200.

## Data

Source: [Stuart Axelbrooke / thoughtvector, Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter). CC BY-NC-SA 4.0; see `DATA_LICENSE.md`. This package is a redacted 2,280-message subsample. Redaction is best-effort.

`data/cohort.json` pins tweet IDs. Rebuild from your own `twcs.csv`:

```bash
python3 src/support.py prepare --input /absolute/path/to/twcs.csv --brand AmazonHelp --out data
```

That writes blank train/dev/test labels. Completed gold lives in `data/gold.csv`.

## Layout

- `src/support.py`: importer, cleaning, retrieval and agent
- `src/workflow.py`: generation, scoring and evidence-chain checks
- `src/evaluation.py`: metrics, bootstrap, Wilson intervals, rating agreement
- `src/judge.py`: blind cached LLM judge
- `src/workbook.py`, `src/import_review.py`, `src/annotate.py`: review artifacts
- `src/report.py`, `src/audit.py`, `src/replay.py`: report, audit and replay
- `tests/`: leakage, redaction, catalog fail-closed, metric denominators, review import

## Attribution

Dataset terms are in `DATA_LICENSE.md`. Application code, tests and documents were written with an AI coding assistant. No third-party application code was copied.
