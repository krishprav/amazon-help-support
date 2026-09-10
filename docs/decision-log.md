# Decision log

1. Select AmazonHelp to study a single retail support scope with enough real examples. This still spans regions and languages.
2. Limit the initial task to root customer messages with direct brand replies. That makes inputs explicit but excludes unanswered traffic and difficult follow-ups.
3. Join every direct brand reply in timestamp order. Keeping just one tweet had produced incomplete fragments such as “(2/2)”.
4. Partition whole customers, then cap the sample. This reduces related conversations appearing on both sides of evaluation.
5. Pin the original inspected cohort by tweet ID. Cleaning improvements must not silently move inspected training examples into the test set.
6. Use eight intents from inspection of 100 training examples. Prefer the requested action over a brand or product mention.
7. Use weak keyword training labels initially and identify them as weak. They are never accepted as human gold labels.
8. Include both a majority-intent baseline and keyword/nearest-reply baseline. This exposes the value of retrieval and routing separately from a generic response.
9. Keep the offline agent dependency-free. Cached output replay needs no network and is easy to explain live.
10. Draw only from training examples, with a narrow source-checked clarification catalog. This limits copied promises, but source support does not imply relevance.
11. Auto-handle only exact social acknowledgements. The trade-off is severe: the included 200-message run automates zero messages.
12. Use a blind matched cohort of 20 messages and all three systems for judge calibration. That provides 60 replies with paired comparisons, but only 20 independent message contexts.
13. Give each system the same evidence packet during judging. Empty evidence for the trivial baseline would unfairly confound model identity and grounding.
14. Report undefined unsafe-auto rate when coverage is zero, and undefined kappa for degenerate ratings. Avoid presenting absence of measurement as perfection.
15. Keep human review blank and fail when required evidence is missing. A completed-looking report with fabricated labels would defeat the point of the assignment.
16. Do not invent LLM-judge scores when the HTTPS provider blocks. An incomplete `results/judge.json` is not a completed evaluation; cached hits may resume later.
