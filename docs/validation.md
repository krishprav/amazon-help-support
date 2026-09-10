# Validation record

- 53 automated tests passed on the included code and blank workbook.
- Full offline generation: 600 predictions for 200 real messages, 2.49 seconds in this environment.
- Partition audit: 2,000 train, 80 dev, 200 test; no shared customer groups, tweet IDs or normalized exact messages.
- Every retrieved/cited evidence ID belongs to the training partition.
- F1 and quadratic weighted kappa matched scikit-learn on independent generated fixtures to a tolerance of 1e-12. Scikit-learn is not a runtime dependency.
- The workbook was rendered and inspected across all four tabs. Blank labels and matching message IDs were verified from the exported XLSX.
- Workbook import was exercised on synthetic fixture labels in a temporary directory. Those fixtures are not the packaged gold set.
- Gold labels (200) and blind ratings (60) are packaged in `data/gold.csv` and `data/human_ratings.csv`. Names are self-attestations.
- A complete 60-reply `results/judge.json` is not packaged. The HTTPS provider blocked later POSTs (HTTP 405 / content-filter). Scores were not invented. `workflow.py check` is expected to fail until a complete judge file exists.
