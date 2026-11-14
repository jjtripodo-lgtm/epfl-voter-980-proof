#!/usr/bin/env python3
"""Second, separately written exact check that a weighted-counter LUT network equals sum(A) >= T.

This file does not import check_generic.py or literal.py. It uses a different terminal
method: it enumerates every assignment of the final weighted frontier (2^|F| cases) with
bit-parallel truth tables, instead of building an ROBDD.

Argument (all inputs assumed in {0,1}):
  1. Start with frontier F = {A[i]: weight 0}. Each metadata group consumes frontier signals
     at their stated weights (and optional constant-one inputs), and produces fresh LUT
     outputs whose fan-in is exactly the consumed signals. For every local assignment with
     local value v <= N + C, we require v - out = 0, or 2^d for a group that declares a
     dropped weight d. By induction, sum(A) + C = S_F + D with 0 <= D < 2^q, where S_F is
     the weighted frontier sum and D the total dropped value. Each local value is at most
     S_F(before) + group constants <= N + C, so skipped local cases are unreachable.
  2. All final frontier weights are >= q and 2^K is a multiple of 2^q, so
     sum(A) >= T  <=>  sum(A) + C >= 2^K  <=>  S_F >= 2^K.
  3. The output cone, cut at the frontier, contains no primary input and no consumed signal.
     For every frontier assignment with S_F <= N + C, the output equals [S_F >= 2^K].
"""
import copy
import hashlib
import json
import sys
from pathlib import Path


def need(ok, why):
    if not ok:
        raise ValueError(why)


def parse(raw):
    text = raw.decode("ascii").replace("\\\n", " ")
    ins, outs, luts, cur, model_seen, ended = [], [], {}, None, False, False
    for line in text.splitlines():
        cols = line.split("#", 1)[0].split()
        if not cols:
            continue
        need(not ended, "content after .end")
        op = cols[0]
        if op == ".model":
            need(not model_seen and len(cols) == 2, "model")
            model_seen, cur = True, None
        elif op == ".inputs":
            ins.extend(cols[1:]); cur = None
        elif op == ".outputs":
            outs.extend(cols[1:]); cur = None
        elif op == ".names":
            need(len(cols) >= 2 and cols[-1] not in luts, "duplicate driver " + cols[-1])
            cur = cols[-1]
            luts[cur] = (cols[1:-1], [])
        elif op == ".end":
            ended, cur = True, None
        elif op.startswith("."):
            raise ValueError("unsupported directive " + op)
        else:
            need(cur is not None, "cube outside .names")
            luts[cur][1].append(cols)
    need(model_seen and ended, "model/end")
    need(len(set(ins)) == len(ins) and not set(ins) & set(luts), "input set")
    for name, (pins, rows) in luts.items():
        need(len(pins) <= 6 and len(set(pins)) == len(pins), "fan-in " + name)
        need(all(p in luts or p in ins for p in pins), "undriven fan-in " + name)
        if pins:
            need(all(len(r) == 2 and len(r[0]) == len(pins) and set(r[0]) <= set("01-")
                     and r[1] in "01" for r in rows), "cube syntax " + name)
            need(len({r[1] for r in rows}) <= 1, "mixed cover polarity " + name)
        else:
            need(rows in ([], [["0"]], [["1"]]), "constant " + name)
    return ins, outs, luts


def lut_table(lut):
    """Return the LUT truth table as a list indexed by sum(bit_i << i) over its pins."""
    pins, rows = lut
    if not pins:
        return [int(rows == [["1"]])]
    table = []
    for a in range(1 << len(pins)):
        bits = [(a >> i) & 1 for i in range(len(pins))]
        hit = any(all(c == "-" or int(c) == b for c, b in zip(r[0], bits)) for r in rows)
        on_set = (not rows) or rows[0][1] == "1"
        table.append(int(hit) if on_set else int(not hit))
    return table


def bit_eval(lut, pin_truths, full):
    """Bit-parallel evaluation of one LUT over all frontier assignments."""
    pins, rows = lut
    if not pins:
        return full if lut_table(lut)[0] else 0
    hit = 0
    for r in rows:
        term = full
        for c, t in zip(r[0], pin_truths):
            if c == "1":
                term &= t
            elif c == "0":
                term &= full ^ t
        hit |= term
    on_set = (not rows) or rows[0][1] == "1"
    return hit if on_set else full ^ hit


def pack(flags):
    """Pack a 0/1 list into an int whose bit a equals flags[a]."""
    out = bytearray((len(flags) + 7) // 8)
    for a, f in enumerate(flags):
        if f:
            out[a >> 3] |= 1 << (a & 7)
    return int.from_bytes(bytes(out), "little")


def audit(raw, meta, N, T):
    need(type(N) is int and type(T) is int and 1 <= T <= N, "case")
    ins, outs, luts = parse(raw)
    need(ins == ["A[%d]" % i for i in range(N)] and outs == ["maj"], "ordered interface")
    need(meta.get("N") == N and meta.get("T") == T and meta.get("output") == "maj", "metadata case")
    K, C = meta.get("K"), meta.get("C")
    q = meta.get("frontier_quantum", K)
    need(all(type(x) is int for x in (K, C, q)) and 0 <= q <= K <= 40, "K/C/q")
    need(C == (1 << K) - T and C >= 0, "offset")
    bound = N + C
    frontier = {s: 0 for s in ins}
    seen = set(ins)
    consumed = set()
    group_outputs = set()
    const_total = 0
    drops = []
    checked = 0
    for g in meta["groups"]:
        real = [(s, w) for s, w in g["inputs"] if s != "__ONE__"]
        const = [w for s, w in g["inputs"] if s == "__ONE__"]
        need(1 <= len(real) <= 6 and len({s for s, _ in real}) == len(real), "group inputs")
        need(all(type(w) is int and 0 <= w <= 40 for _, w in g["inputs"] + g["outputs"]), "weights")
        need(all(frontier.get(s) == w for s, w in real), "input not on frontier at stated weight")
        names = [s for s, _ in real]
        d = g.get("dropped_sum_weight")
        need(d is None or (type(d) is int and 0 <= d < q and d not in drops), "drop rule")
        if d is not None:
            drops.append(d)
        const_total += sum(1 << w for w in const)
        tables = []
        for s, w in g["outputs"]:
            need(s not in seen and s in luts and set(luts[s][0]) == set(names), "output driver " + s)
            pins = luts[s][0]
            t = lut_table(luts[s])
            # Re-index the LUT table to the group's input order.
            pos = [names.index(p) for p in pins]
            tables.append(([t[sum(((a >> pos[i]) & 1) << i for i in range(len(pins)))]
                            for a in range(1 << len(names))], w))
        tables = [(list(t), w) for t, w in tables]
        for a in range(1 << len(names)):
            v = sum(((a >> i) & 1) << w for i, (_, w) in enumerate(real)) + sum(1 << w for w in const)
            if v > bound:
                continue
            out = sum(t[a] << w for t, w in tables)
            need(v - out == 0 or (d is not None and v - out == 1 << d), "local weighted identity")
            checked += 1
        for s in names:
            del frontier[s]
            consumed.add(s)
        for s, w in g["outputs"]:
            frontier[s] = w
            seen.add(s)
            group_outputs.add(s)
    need(const_total == C, "constant total")
    need(all(w >= q for w in frontier.values()), "frontier below quantum")
    need(sorted(frontier.items()) == sorted(map(tuple, meta["frontier"])), "frontier binding")
    need((1 << K) % (1 << q) == 0, "target lattice")
    # Output cone cut at the frontier.
    order, state = [], {}

    def walk(s):
        if s in frontier or state.get(s) == 2:
            return
        need(s in luts and s not in group_outputs and s not in ins, "terminal bypass at " + s)
        need(state.get(s) != 1, "cycle")
        state[s] = 1
        for p in luts[s][0]:
            walk(p)
        state[s] = 2
        order.append(s)

    walk("maj")
    fs = sorted(frontier)
    n = len(fs)
    need(n <= 24, "frontier too large for enumeration")
    full = (1 << (1 << n)) - 1
    truth = {}
    for i, s in enumerate(fs):
        truth[s] = pack([(a >> i) & 1 for a in range(1 << n)])
    for s in order:
        truth[s] = bit_eval(luts[s], [truth[p] for p in luts[s][0]], full)
    weights = [1 << frontier[s] for s in fs]
    ssum = [0] * (1 << n)
    for a in range(1, 1 << n):
        low = (a & -a).bit_length() - 1
        ssum[a] = ssum[a & (a - 1)] + weights[low]
    care = pack([x <= bound for x in ssum])
    want = pack([x >= (1 << K) for x in ssum])
    need(((truth["maj"] ^ want) & care) == 0, "terminal does not equal threshold on reachable frontier")
    return {"PASS": True, "N": N, "T": T, "K": K, "C": C, "Q": 1 << q, "groups": len(meta["groups"]),
            "local_assignments": checked, "frontier_bits": n, "frontier_assignments": 1 << n,
            "reachable_frontier_assignments": bin(care).count("1"), "terminal_nodes": len(order),
            "netlist_sha256": hashlib.sha256(raw).hexdigest()}


def main():
    raw = Path(sys.argv[1]).read_bytes()
    meta = json.loads(Path(sys.argv[2]).read_text())
    N, T = int(sys.argv[3]), int(sys.argv[4])
    result = audit(raw, meta, N, T)
    rejected = []
    hostile = [
        ("threshold_plus_one", raw, meta, N, T + 1),
        ("frontier_weight_changed", raw, None, N, T),
        ("first_group_cover_row_removed", None, meta, N, T),
    ]
    for name, r, m, n, t in hostile:
        if m is None:
            m = copy.deepcopy(meta)
            m["frontier"][0][1] += 1
        if r is None:
            text = raw.decode("ascii")
            first = meta["groups"][0]["outputs"][0][0]
            head = next(line for line in text.splitlines() if line.startswith(".names ") and line.split()[-1] == first)
            start = text.index(head + "\n") + len(head) + 1
            stop = text.index("\n", start) + 1
            r = (text[:start] + text[stop:]).encode("ascii")
        try:
            audit(r, m, n, t)
        except ValueError:
            rejected.append(name)
        else:
            raise SystemExit("FAIL: accepted hostile control " + name)
    result["hostile_controls_rejected"] = rejected
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
