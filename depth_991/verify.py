#!/usr/bin/env python3
"""Fail-closed, standalone exact verification of the EPFL VOTER 991-LUT6 / depth-8 BLIF."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from structure import inspect

ROOT = Path(__file__).resolve().parent
EXPECTED_PINS = {
    "best_results/depth/voter_depth_2027.blif": "79dab10ff9673246a4775e86553ef44dc4394506e5604077ea6e22cb642d7721",
    "licenses/epfl_benchmarks_mit.txt": "83e4dd21429a91fb7cea67a476032a9641425e5355df2e0f589a738b6ec9fd2c",
    "proof/audit_bdd_core_fast.cpp": "c747378528655568aec4ef1a786c83871885b9be72148b6c5a3b0b64545b4022",
    "proof/bdd_replay_fast.cpp": "42e341e796ea9a3bd478f7147a1b59e146ef18ebf2b2c24ef13869b4de02bfd2",
    "proof/check_frontier_enum.py": "2b0bf1e13a0a6d26fbff7742f9636695d249aeb884b426c111e310cfdd31d39e",
    "proof/check_generic.py": "c913da04e36184656d555f09026d5024313e7e4249935b180f78ad17a4482e29",
    "proof/literal.py": "4330ce74c38aa5eae5b7bbb57c67bf404fc985d75df6a8845f22474b489e646f",
    "proof/original_exact.plan": "32e2741559aefcb21206552bf782dcbc25e9bd182c764cbaf1a67bdfd5927a35",
    "proof/verify_original_bdd_plan.py": "0eb49e2a3be6434ee36364e6e939bd55c6c89b2ead9b476e8b5fca211f14c056",
    "proof/verify_voter_independent.py": "13e4fda4fbc6531dcf056c1887f46181a96992e47ee51c8a83b803af27f9969e",
    "source/staged_tuned_991_8.blif": "22d7bdf150817c107226f0c5f9a147823c7d32c1279f67a1337fe60a15f482f6",
    "source/staged_tuned_991_8.blif.meta.json": "29dc9b986ae7e04703bda17c9ccaaa40d9fc02c46bc3b340e0139f4e2806c541",
    "source/voter_original.blif": "542214e933efbcd563aebf9a3a7487dfb596c823af2e62f72b105b2dae1ed597",
    "structure.py": "00ae091d54bf0fec42dccbc6a5f57942974796142cdeb74e9c9b41224269deae"
}
EXPECTED = {"depth": (991, 8)}
FILES = {
    "original": "source/voter_original.blif",
    "depth_parent": "source/staged_tuned_991_8.blif",
    "depth": "best_results/depth/voter_depth_2027.blif",
}


class VerificationError(Exception):
    pass


def need(condition, message):
    if not condition:
        raise VerificationError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(command, timeout, cwd=ROOT):
    start = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                                   timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise VerificationError(f"TIMEOUT after {timeout}s: {command[0]}") from exc
    need(completed.returncode == 0,
         f"COMMAND_FAILED ({completed.returncode}): {' '.join(map(str, command))}\n"
         f"stdout: {completed.stdout[-1600:]}\nstderr: {completed.stderr[-1600:]}")
    return completed.stdout, time.monotonic() - start


def require_json(command, timeout, expected):
    out, seconds = run(command, timeout)
    try:
        result = json.loads(out)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid checker JSON: {command[-1]}: {out[-500:]}") from exc
    need(result.get("PASS") is True, "checker did not assert PASS")
    for key, value in expected.items():
        need(result.get(key) == value, f"unexpected checker {key}: {result.get(key)}")
    return {"seconds": round(seconds, 3), "result": result}


def check_pins():
    manifest_bytes = (ROOT / "PINNED_FILES.json").read_bytes()
    pins = json.loads(manifest_bytes)
    need(pins == EXPECTED_PINS, "pin manifest changed")
    for relative, expected in pins.items():
        path = ROOT / relative
        need(path.is_file() and sha(path.read_bytes()) == expected,
             f"SHA256 mismatch: {relative}")
    return pins


def abc_result(abc, first, second, timeout, equivalent=True):
    command = [abc, "-c", f"cec -n {first} {second}"]
    out, seconds = run(command, timeout)
    if equivalent:
        need(re.search(r"Networks are equivalent(?: after structural hashing)?\.", out) is not None
             and "NOT EQUIVALENT" not in out, f"ABC gave no equivalence proof: {out[-1000:]}")
    else:
        need("Networks are NOT EQUIVALENT." in out,
             f"ABC did not report inequivalence: {out[-1000:]}")
    return {"seconds": round(seconds, 3), "verdict": "EQUIVALENT" if equivalent else "INEQUIVALENT",
            "tool_output": out.strip()[:1000]}


def one_output_lut(data):
    """Set the final maj LUT to one; all-zeros is a clear mismatch witness."""
    lines = data.decode("ascii").splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith(".names ") and line.split()[-1] == "maj"]
    need(len(starts) == 1, "cannot locate unique output LUT")
    start = starts[0]
    stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(".")), len(lines))
    need(stop > start + 1, "output LUT has no cover rows")
    pin_count = len(lines[start].split()) - 2
    return "".join(lines[:start + 1] + ["-" * pin_count + " 1\n"] + lines[stop:]).encode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="skip the expensive original-to-majority ROBDD replay")
    parser.add_argument("--abc-timeout", type=float, default=120.0, help="seconds allowed per ABC call (default: 120)")
    args = parser.parse_args()
    if args.abc_timeout <= 0:
        parser.error("--abc-timeout must be positive")
    report = {"mode": "fast" if args.fast else "full", "checks": {}, "overall": "INCOMPLETE"}
    print("EPFL VOTER 991/8 DEPTH VERIFICATION", flush=True)
    try:
        pins = check_pins()
        print(f"SHA256: PASS ({len(pins)} pinned files)", flush=True)
        report["checks"]["sha256"] = "PASS"
        for name in ("depth",):
            stats = inspect((ROOT / FILES[name]).read_bytes())
            need((stats["lut6"], stats["depth"]) == EXPECTED[name], f"{name} LUT/depth mismatch")
            print(f"{name}: port/interface PASS; {stats['lut6']} LUT6 / depth {stats['depth']} PASS", flush=True)
            report["checks"][name + "_structure"] = stats
        python = sys.executable
        proof = ROOT / "proof"
        source = ROOT / "source"
        plan = proof / "original_exact.plan"
        original = source / "voter_original.blif"
        out, seconds = run([python, str(proof / "verify_original_bdd_plan.py"), str(original), str(plan)], 120)
        binding = json.loads(out)
        need(binding.get("status") == "PASS" and binding.get("inputs") == 1001
             and binding.get("gates") == 13758, "original-source-to-plan binding failed")
        report["checks"]["original_plan_binding"] = {"seconds": round(seconds, 3), "result": binding}
        print("Original source-to-ROBDD plan: PASS", flush=True)
        parent = str(source / "staged_tuned_991_8.blif")
        meta = str(source / "staged_tuned_991_8.blif.meta.json")
        first = require_json([python, str(proof / "check_generic.py"), parent, meta, "1001", "501", "offset"], 300,
                             {"N": 1001, "T": 501, "groups": 330, "local_assignments": 20856, "frontier_bits": 19,
                              "paid_lut6": 991, "depth": 8,
                              "netlist_sha256": EXPECTED_PINS["source/staged_tuned_991_8.blif"]})
        need(len(first["result"].get("hostile_controls_rejected", [])) == 6, "checker 1 hostile controls")
        report["checks"]["depth_parent_checker_1_robdd_terminal"] = first
        second = require_json([python, str(proof / "check_frontier_enum.py"), parent, meta, "1001", "501"], 300,
                              {"N": 1001, "T": 501, "groups": 330, "local_assignments": 20856, "frontier_bits": 19,
                               "terminal_nodes": 8,
                               "netlist_sha256": EXPECTED_PINS["source/staged_tuned_991_8.blif"]})
        need(len(second["result"].get("hostile_controls_rejected", [])) == 3, "checker 2 hostile controls")
        report["checks"]["depth_parent_checker_2_frontier_enumeration"] = second
        print("depth parent = majority: PASS (two separately written checkers)", flush=True)
        abc = os.environ.get("ABC_BIN") or shutil.which("yosys-abc") or shutil.which("abc")
        need(abc is not None, "ABC unavailable; install Yosys ABC or set ABC_BIN")
        version, _ = run([abc, "-c", "version"], 20)
        report["abc_version"] = version.strip()
        with tempfile.TemporaryDirectory(prefix="voter_verify_") as tmp:
            for name in ("depth",):
                parent = ROOT / FILES[name + "_parent"]
                final = ROOT / FILES[name]
                report["checks"][name + "_parent_final_cec"] = abc_result(abc, parent, final, args.abc_timeout)
                mutant = Path(tmp) / (name + "_forced_one.blif")
                mutant.write_bytes(one_output_lut(final.read_bytes()))
                report["checks"][name + "_negative_control"] = abc_result(abc, parent, mutant, args.abc_timeout, False)
                print(f"{name} parent = final: PASS; mutated output: REJECTED", flush=True)
            if args.fast:
                report["checks"]["original_majority_robdd"] = "NOT_RUN"
                print("Original = majority: NOT_RUN (--fast)", flush=True)
            else:
                compiler = os.environ.get("CXX") or shutil.which("c++")
                need(compiler is not None, "C++17 compiler unavailable")
                audit_executable = Path(tmp) / "audit_bdd_core"
                _, audit_compile_seconds = run([compiler, "-std=c++17", "-O2", str(proof / "audit_bdd_core_fast.cpp"), "-o", str(audit_executable)], 120)
                audit_output, audit_seconds = run([str(audit_executable)], 120)
                audit = json.loads(audit_output)
                need(audit.get("status") == "PASS" and audit.get("live_root_truth_checks") == 20480000
                     and audit.get("threshold_truth_checks") == 106494,
                     "ROBDD kernel audit failed")
                report["checks"]["robdd_kernel_audit"] = {"compile_seconds": round(audit_compile_seconds, 3),
                    "seconds": round(audit_seconds, 3), "result": audit}
                print("ROBDD kernel finite controls: PASS", flush=True)
                executable = Path(tmp) / "bdd_replay"
                _, compile_seconds = run([compiler, "-std=c++17", "-O3", str(proof / "bdd_replay_fast.cpp"), "-o", str(executable)], 120)
                out, seconds = run([str(executable), str(plan), "501"], 900)
                bdd = json.loads(out)
                need(bdd.get("equal") is True and bdd.get("inputs") == 1001
                     and bdd.get("gates") == 13758 and bdd.get("threshold") == 501,
                     "ROBDD did not prove original = majority")
                report["checks"]["original_majority_robdd"] = {"compile_seconds": round(compile_seconds, 3),
                    "seconds": round(seconds, 3), "result": bdd}
                print("Original = majority: PASS (full ROBDD replay)", flush=True)
                report["overall"] = "VERIFIED"
        print("OVERALL: " + report["overall"], flush=True)
    except (VerificationError, OSError, UnicodeError, ValueError, KeyError) as exc:
        report["error"] = str(exc)
        print("OVERALL: FAILED - " + str(exc), file=sys.stderr, flush=True)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if args.fast else 0


if __name__ == "__main__":
    sys.exit(main())
