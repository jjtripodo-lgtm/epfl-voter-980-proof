# EPFL VOTER: independent exact verification of the 980-LUT6 size candidate

This repository accompanies a proposed **single** EPFL VOTER size-table implementation:
`best_results/size/voter_size_2027.blif`, **980 reachable LUT6 nodes at depth 12**.
The implementation has 1,001 ordered inputs `A[0]` through `A[1000]`, one output `maj`, and maximum LUT fan-in six.

## Reproduce the proof

Requirements: Python 3.10 or later, a C++17 compiler, and Berkeley ABC 1.01 (or a compatible version). When ABC is not on `PATH` as `abc` or `yosys-abc`, point `ABC_BIN` to it.

```sh
./verify.sh
# or:
ABC_BIN=/path/to/abc ./verify.sh
```

A completed exact check exits **0** and reports `OVERALL: VERIFIED`. A changed input, solver failure, timeout, or inconclusive ABC result does not produce a successful verdict. The optional `./verify.sh --fast` is an integrity preflight only: it prints `OVERALL: INCOMPLETE` and exits 2.

The verifier checks 17 frozen source, proof, metadata, and license files against the hashes in `PINNED_FILES.json`; checks the final BLIF interface and 980-LUT6/depth-12 structure; and replays the following complete proof:

1. **Official original = majority:** the original 13,758-gate VOTER network is bound to its exact source plan, then a dependency-free reduced ordered binary decision diagram (ROBDD) replay proves equality to `sum(A[0..1000]) >= 501`.
2. **Weighted-count parent = majority:** two independent literal-cover checkers verify the actual `source/mixed_980_12.blif` network, including 332 groups and 21,092 local assignments, and its final threshold decision.
3. **Final BLIF = parent:** ABC `cec -n` returns an explicit equivalence verdict between the parent and final `best_results/size/voter_size_2027.blif`. The verifier also requires an explicit **inequivalence** verdict for a deliberately altered output LUT.

By transitivity, the frozen submitted BLIF equals the official VOTER function for **all** `2^1001` primary-input assignments. Direct original-to-final ABC attempts did not finish within the tested budgets, so the independently replayable transitive proof is the proof of record.

A complete clean-copy replay on 7 November 2026 reported `OVERALL: VERIFIED` with exit 0, took 88.40 seconds, and peaked at 1.87 GiB on an Apple M4 machine running macOS. Runtime and memory will vary with platform and toolchain.

## Frozen identities

| Source | SHA-256 |
| --- | --- |
| Original `source/voter_original.blif` | `542214e933efbcd563aebf9a3a7487dfb596c823af2e62f72b105b2dae1ed597` |
| Parent `source/mixed_980_12.blif` | `56d1815ffb63fe65240809bde1be4435f4aecee43f29137b573e8766d50a0f4a` |
| Candidate `best_results/size/voter_size_2027.blif` | `1172cc9d7b4b7ecd44dae7ef3d721127965d9311fbf119c7c8cca58abfa5c18e` |

## Provenance and limits

The original VOTER benchmark is from `lsils/benchmarks`; its upstream MIT license notice is retained at `licenses/epfl_benchmarks_mit.txt`. That notice describes the upstream benchmark rights; it should not be interpreted as a blanket license statement for independently written verifier code.

## Author and license

Author: John Tripodo, Independent researcher. Claude (Anthropic) and ChatGPT (OpenAI) assisted circuit search, synthesis and verification code, solver runs, audits, and documentation. John selected and directed the work and is responsible for the submission.

The original EPFL benchmark retains its upstream notice at `licenses/epfl_benchmarks_mit.txt`. The following MIT license applies to John Tripodo's contributions in this repository, including the candidate, parent, proof sources, and verification code:

MIT License

Copyright (c) 2026 John Tripodo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This verification establishes functional equivalence of the frozen candidate, not a global optimum, routed-FPGA timing result, direct-miter proof certificate, or EPFL organizer acceptance. The trusted software base includes the included checker implementations, SHA-256, the C++ compiler, and ABC. The saved timing report is background evidence; **run the verifier** to generate a fresh verdict.
