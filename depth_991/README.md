# EPFL VOTER: exact verification of the 991-LUT6, depth-8 candidate

This repository accompanies a proposed EPFL VOTER depth-table implementation:
`best_results/depth/voter_depth_2027.blif`, **991 LUT6 nodes at depth 8**.
The implementation has 1,001 ordered inputs `A[0]` through `A[1000]`, one output `maj`, and maximum LUT fan-in six. It contains no 1-input buffers.

## Reproduce the proof

Requirements: Python 3.10 or later, a C++17 compiler, and Berkeley ABC 1.01 (or a compatible version). When ABC is not on `PATH` as `abc` or `yosys-abc`, point `ABC_BIN` to it.

```sh
./verify.sh
# or:
ABC_BIN=/path/to/abc ./verify.sh
```

A completed exact check exits **0** and reports `OVERALL: VERIFIED`. A changed input, checker failure, timeout, or inconclusive ABC result does not produce a successful verdict. The optional `./verify.sh --fast` skips the original-to-majority ROBDD replay; it prints `OVERALL: INCOMPLETE` and exits 2.

The verifier checks 14 frozen source, proof, metadata and license files against the hashes in `PINNED_FILES.json`, checks the final BLIF interface and its 991-LUT6 / depth-8 structure, and replays this proof:

1. **Official original = majority.** The original 13,758-gate VOTER network is bound to an exact source plan. A dependency-free reduced ordered binary decision diagram (ROBDD) replay then proves that it equals `sum(A[0..1000]) >= 501`. This step and its files are the same as in the earlier VOTER size proof package (`jjtripodo-lgtm/epfl-voter-980-proof`).
2. **Weighted-counter parent = majority.** `source/staged_tuned_991_8.blif` is a weighted-counter network: 330 LUT groups, each of which replaces up to six weighted bits with fewer weighted bits that hold the same local sum (one group may drop a declared value of 1, which cannot change the decision), with the constant 11 folded in so that the decision becomes `sum(A) + 11 >= 512`. Two separately written checkers read the actual LUT covers, not only the metadata:
   - `proof/check_generic.py` checks all 20,856 local group assignments and then compares the 8-LUT terminal with the threshold by an exact ROBDD over the 19 frontier bits.
   - `proof/check_frontier_enum.py` (does not import the first checker) repeats the local check and then enumerates all 2^19 frontier assignments with bit-parallel truth tables.
   Each checker also requires rejection of altered inputs (for example a wrong threshold or a removed cover row).
3. **Final BLIF = parent.** ABC `cec -n` returns an explicit equivalence verdict between the parent and `best_results/depth/voter_depth_2027.blif`. The verifier also requires an explicit **inequivalence** verdict for a copy whose output LUT is forced to one.

By transitivity, the submitted BLIF equals the official VOTER function for **all** `2^1001` primary-input assignments.

A direct ABC `cec` from the original to the final BLIF ran for 55 minutes without a verdict (timeout). We do not claim a direct original-to-final ABC result; the transitive proof above is the proof of record.

A clean-copy replay on 13 November 2026 reported `OVERALL: VERIFIED` with exit 0 in 216 seconds, with a peak child resident set of about 2.9 GiB (Linux, Berkeley ABC 1.01). The ROBDD replay takes most of that time. Runtime and memory change with platform and toolchain.

## Frozen identities

| Source | SHA-256 |
| --- | --- |
| Original `source/voter_original.blif` | `542214e933efbcd563aebf9a3a7487dfb596c823af2e62f72b105b2dae1ed597` |
| Parent `source/staged_tuned_991_8.blif` | `22d7bdf150817c107226f0c5f9a147823c7d32c1279f67a1337fe60a15f482f6` |
| Candidate `best_results/depth/voter_depth_2027.blif` | `79dab10ff9673246a4775e86553ef44dc4394506e5604077ea6e22cb642d7721` |

## Provenance and limits

The original VOTER benchmark is from `lsils/benchmarks`; its upstream MIT license notice is retained at `licenses/epfl_benchmarks_mit.txt`.

The candidate was built independently by a weighted-counter (compressor-tree) construction for the 1,001-input popcount, with constant folding of the threshold, exact encoding of the final cofactor classes, and exact removal of redundant support. Weighted counting and compressor trees are established methods; this is a benchmark-specific result, not a claim of a new general synthesis algorithm.

This verification establishes functional equivalence of the frozen candidate. It does not establish a global optimum, a routed-FPGA timing result, or EPFL organizer acceptance. The trusted base includes the included checkers, SHA-256, the C++ compiler, and ABC.

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
