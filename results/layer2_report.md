# Layer 2 Basic Report

## Scope

This report summarizes only the Layer 2 Wasmtime results.

Tested variants:

- CLEAN_CODEC
- B001_CODEC
- B003_CODEC

Execution setup:

- Runtime: Wasmtime
- Modes: `start` and `invoke`
- Matrix command:

```bash
WASI_MODE=fast WASI_REPEAT_RUNS=1 ./scripts/run_layer2_matrix.sh CLEAN_CODEC:. B001_CODEC:. B003_CODEC:.
```

## Results Summary

| Bug ID      | Total Rows | Fail Rows | Detection | Main Failure Type |
| ----------- | ---------: | --------: | --------- | ----------------- |
| CLEAN_CODEC |         41 |         0 | no        | none              |
| B001_CODEC  |         41 |        38 | yes       | output mismatch   |
| B003_CODEC  |         41 |         2 | yes       | trap              |

## Key Findings

1. Layer 2 correctly keeps the clean baseline stable.
   CLEAN_CODEC produced 41 passes and 0 failures.

2. Layer 2 is effective at catching logic bugs that change output.
   B001_CODEC was detected with 38 output mismatches.

3. Layer 2 is also effective at catching runtime trap bugs.
   B003_CODEC was detected with 2 trap failures.

4. Both execution paths contributed to coverage.
   All three variants were exercised in both `start` and `invoke` mode.

## Per-Mode Notes

- B001_CODEC:
  - `start`: 34 failures out of 36 rows
  - `invoke`: 4 failures out of 5 rows

- B003_CODEC:
  - `start`: 1 trap out of 36 rows
  - `invoke`: 1 trap out of 5 rows

## Interpretation

Layer 2 is good at detecting bugs inside the Wasm module itself.

- It catches wrong output behavior.
- It catches runtime trap behavior.
- It provides stronger confidence than only running a clean baseline.

Layer 2 is less suitable for bugs caused by JavaScript/browser-side integration.
For example, `B002_CODEC` is described as a boundary bug caused by the JS side passing the wrong length. That type of issue belongs mainly to Layer 3 rather than Layer 2.

## Basic Recommendations

1. Keep `CLEAN_CODEC`, `B001_CODEC`, and `B003_CODEC` in the Layer 2 matrix.
2. Use both `start` and `invoke` mode, because they catch module behavior through different entry paths.
3. Keep at least one clean baseline in every matrix run, so bug detection is easy to compare.
4. Do not rely on Layer 2 alone for JS boundary bugs such as `B002_CODEC`; validate those in Layer 3.

## Final Conclusion

For a basic Layer 2 deliverable, the current setup is sufficient:

- the harness is stable,
- the matrix runs successfully,
- the analysis and chart generation work,
- and Layer 2 can distinguish clean behavior from at least one logic bug and one trap bug.
