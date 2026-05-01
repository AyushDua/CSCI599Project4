# Layer 2 Basic Report

## Scope

This report summarizes only the Layer 2 Wasmtime results.

Tested variants:

- CLEAN_CODEC
- B001_CODEC
- B002_CODEC
- B003_CODEC

Execution setup:

- Runtime: Wasmtime
- Modes: `start` and `invoke`
- Matrix command:

```bash
WASI_MODE=fast WASI_REPEAT_RUNS=1 ./scripts/run_layer2_matrix.sh CLEAN_CODEC:. B001_CODEC:. B002_CODEC:. B003_CODEC:.
```

## Results Summary

| Bug ID      | Total Rows | Fail Rows | Detection | Main Failure Type |
| ----------- | ---------: | --------: | --------- | ----------------- |
| CLEAN_CODEC |         47 |         0 | no        | none              |
| B001_CODEC  |         47 |        44 | yes       | output mismatch   |
| B002_CODEC  |         47 |         6 | yes       | output mismatch   |
| B003_CODEC  |         47 |         2 | yes       | trap              |

## Key Findings

1. Layer 2 correctly keeps the clean baseline stable.
   CLEAN_CODEC produced 47 passes and 0 failures.

2. Layer 2 is effective at catching logic bugs that change output.
   B001_CODEC was detected with 44 output mismatches.

3. Layer 2 also detects UTF-8 boundary truncation.
   B002_CODEC was detected with 6 output mismatches, all on the new UTF-8-focused cases.

4. Layer 2 is also effective at catching runtime trap bugs.
   B003_CODEC was detected with 2 trap failures.

5. Both execution paths contributed to coverage.
   All four variants were exercised in both `start` and `invoke` mode.

## Per-Mode Notes

- B001_CODEC:
  - `start`: 37 failures out of 39 rows
  - `invoke`: 7 failures out of 8 rows

- B002_CODEC:
  - `start`: 3 failures out of 39 rows
  - `invoke`: 3 failures out of 8 rows
  - Failures are concentrated in the `utf8` family rather than ASCII, random, or boundary-length byte cases.

- B003_CODEC:
  - `start`: 1 trap out of 39 rows
  - `invoke`: 1 trap out of 8 rows

## Interpretation

Layer 2 is good at detecting bugs inside the Wasm module itself.

- It catches wrong output behavior.
- It now catches the simulated UTF-8 length mismatch represented by `B002_CODEC`.
- It catches runtime trap behavior.
- It provides stronger confidence than only running a clean baseline.

The updated Layer 2 harness now includes UTF-8-specific cases in both `start` and `invoke` mode, so it can detect a Layer 2 version of the B002 behavior.
That said, Layer 3 is still the best place to validate the full JavaScript-to-Wasm integration path, because the real production bug originates at that boundary.

## Basic Recommendations

1. Keep `CLEAN_CODEC`, `B001_CODEC`, `B002_CODEC`, and `B003_CODEC` in the Layer 2 matrix.
2. Use both `start` and `invoke` mode, because they catch module behavior through different entry paths.
3. Keep the UTF-8-specific cases (`é`, `你好`, `€`) because they are the shortest path to exposing `B002_CODEC`.
4. Keep at least one clean baseline in every matrix run, so bug detection is easy to compare.
5. Do not rely on Layer 2 alone for JS boundary bugs; validate the end-to-end JS/Wasm path in Layer 3 as well.

## Final Conclusion

For a basic Layer 2 deliverable, the current setup is sufficient:

- the harness is stable,
- the matrix runs successfully,
- the analysis and chart generation work,
- and Layer 2 can distinguish clean behavior from a logic bug, a UTF-8 boundary bug, and a trap bug.
