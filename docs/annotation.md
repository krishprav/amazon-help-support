# Sampling and annotation protocol

The packaged gold set has 200 labels and 60 ratings from named annotator CB. Gold used the customer message only (no model predictions or historical replies). Reply ratings used the blinded 60-draft packets. Names are self-attestations. The workbook file remains a blank template so a second reviewer can repeat the protocol.

The 200-message test cohort was sampled from customer root messages with a direct AmazonHelp reply. The source yielded 76,799 eligible pairs before normalized deduplication. Seed 42 shuffled hashed customer groups; complete groups went into test, dev and train, then each partition was capped. The pinned original cohort contains 200 test, 80 dev and 2,000 training messages. All direct brand replies are now joined chronologically. The exact tweet membership is recorded in data/cohort.json and does not change when redaction changes.

Root-only selection, answered-message selection, customer grouping and caps are sampling choices, not a representative sample of all Amazon support traffic. Missing parent references can hide earlier context. Multi-part public replies do not establish that an issue was resolved. Non-English messages and missing-image references remain in the sample.

Inspect training messages before fixing the taxonomy. The coding assistant inspected 100 training examples and defined eight intents; these are not human gold labels. The Guide tab defines them. Choose the primary requested action and explain ambiguity. Where language or context is not interpretable, label other and escalate with a specific reason.

Complete Gold labels before Reply ratings. Do not inspect historical replies or model predictions while labelling gold. For each message enter intent, escalation 0/1, reason and your actual name or consistent reviewer ID. Escalation means the request needs human account access, policy checking or judgment; it does not mean “the model escalated this”. A routine acknowledgement can be 0. An account action or unresolved ambiguity should be 1.

Blind reply ratings use 20 randomly sampled test message IDs (seed 71), with all three systems' replies, then shuffled. Review IDs obscure model identity. Each candidate for a message receives the same union of retrieved and cited historical evidence. Rate grounding, relevance, safety and clarity from 1–5 independently. Use 2 and 4 for intermediate cases. Write a short rationale. Do not open review_mapping.json or judge results before finishing. Style may still reveal system identity, so the blinding is imperfect.

Run the judge after human rating or keep its output inaccessible until ratings are frozen. Record exact agreement, mean absolute error, within-one agreement and quadratic weighted kappa. Review disagreements of at least two points. The 60 replies share 20 customer contexts and are correlated. Do not interpret them as 60 independent message samples.

Human provenance is self-attested; code validates fields, IDs and unchanged text, not a person's identity. AI suggestions should not be submitted as independently hand-labelled examples. If labels or rules change after test inspection, record the change and evaluate on a new held-out cohort.
