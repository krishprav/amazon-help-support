# Training-data inspection

The coding assistant inspected the first 100 examples in the original pinned training partition before generating the current test predictions. Recurring themes included delivery delays, cancelled memberships, billing, device/app issues, damaged contents, seller-account access, praise and general complaints. The eight-intent schema is documented in annotation.md.

These inspections are development notes, not human gold labels. Example training IDs: 314474 (cancelled membership charge), 1387295 (unshipped order), 1662572 (seller-account access), 2513646 (damaged packaging), and 2217276 (late delivery). The source-checked clarification catalog uses only rows present in the training file at runtime.

The first importer kept a single brand reply by ID, which sometimes retained a partial multi-tweet message. The current importer joins all direct brand responses in timestamp order. The original cohort is pinned so this correction does not move previously inspected training messages into test.

The source contains multiple languages, missing images, inconsistent spelling, dates, names and personal identifiers. Masking handles, URLs, emails, order IDs and long number sequences does not guarantee complete anonymization. Removing URLs also removes potentially useful resolution details. Root-message selection excludes follow-ups and unanswered requests. The dataset records replies, not independently verified resolutions.
