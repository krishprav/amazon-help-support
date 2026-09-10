# Validation record

- 30 automated tests passed on the included code and blank workbook.
- Full offline generation: 600 predictions for 200 real messages, 2.49 seconds in this environment.
- Partition audit: 2,000 train, 80 dev, 200 test; no shared customer groups, tweet IDs or normalized exact messages.
- Every retrieved/cited evidence ID belongs to the training partition.
- F1 and quadratic weighted kappa matched scikit-learn on independent generated fixtures to a tolerance of 1e-12. Scikit-learn is not a runtime dependency.
- The workbook was rendered and inspected across all four tabs. Blank labels and matching message IDs were verified from the exported XLSX. Progress formulas were checked with incomplete/complete temporary inputs and restored to blanks.
- Workbook import was exercised on synthetic fixture labels in a temporary directory. These are software tests, not human annotations, and no generated fixture labels are included as gold.
- Live LLM generation and judging were not run: credentials were unavailable.
- The human-gold replay cannot be completed until actual labels and ratings are supplied. The submission evidence check is expected to fail while these files are absent.
