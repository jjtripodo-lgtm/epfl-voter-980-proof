#!/usr/bin/env python3
"""Compositional proof check (carry-only variant with constant offset and dropped sum bits).

Claim checked: BLIF output == [popcount(inputs) >= T] for ALL 2^N inputs.
Extra rules versus check_count_network.py: the metadata names K and C; C must
equal 2^K - T with N + C < 2^(K+1). Group inputs may be the constant '__ONE__'
(value 1, not a LUT pin); the multiset of constant weights used must sum to C,
each weight w < K at most once. A group may drop its weight-w0 sum bit: then
V - sum(outputs) must be 0 or 2^w0 for every admissible V, and dropped weights
must be distinct and < K. Then S + C = F + D with 0 <= D < 2^K, every final
frontier bit has weight >= K, so S >= T iff F >= 2^K; the compare region must
compute exactly [F >= 2^K] on every frontier assignment with F <= N + C.

Usage: check_count_network.py FILE.blif FILE.meta.json
Trusts nothing in the metadata except as a claim to be verified:
 1. Strict BLIF parse; each node's function is read from its own cover.
 2. Every paid node (>=2 fanins) has <= 6 fanins; reachable from the output.
 3. Frontier invariant: start with every primary input at weight 0. Process the
    claimed groups in order. A group's inputs must be distinct members of the
    current frontier at the claimed weights; each output node must have exactly
    the group's input list as its fanins. Exhaustively over all 2^k input values
    whose weighted value V = sum v_i 2^{w_i} is <= N, the outputs must satisfy
    sum o_j 2^{u_j} == V. Inputs are removed and outputs added to the frontier.
    Hence sum over the frontier of b*2^w == popcount(x) <= N for every x
    (induction; any group's V is bounded by the frontier sum).
 4. Every node not in a group (the compare region) reads only final-frontier
    signals or compare-region nodes. Exhaustively over all assignments of the
    final frontier with weighted sum <= N, the output equals [sum >= T].
 5. Every paid node belongs to exactly one group or the compare region.
"""
import itertools
import json
import sys


def fail(m):
    raise SystemExit('FAIL: ' + m)


def parse(path):
    text = open(path, encoding='ascii').read().replace('\\\n', ' ')
    ins, outs, nodes, cur = [], [], {}, None
    for raw in text.split('\n'):
        t = raw.split()
        if not t or t[0].startswith('#'):
            continue
        k = t[0]
        if k in ('.model', '.end'):
            cur = None
        elif k == '.inputs':
            ins += t[1:]; cur = None
        elif k == '.outputs':
            outs += t[1:]; cur = None
        elif k == '.names':
            if t[-1] in nodes or t[-1] in t[1:-1]:
                fail('bad driver ' + t[-1])
            nodes[t[-1]] = (t[1:-1], []); cur = t[-1]
        elif k.startswith('.'):
            fail('unsupported ' + k)
        else:
            if cur is None:
                fail('row outside .names')
            pins = nodes[cur][0]
            if len(t) != 2 or len(t[0]) != len(pins) or t[1] not in '01' or set(t[0]) - set('01-'):
                if not (len(pins) == 0 and t in (['0'], ['1'])):
                    fail('bad row in ' + cur)
            nodes[cur][1].append(t)
    if len(set(ins)) != len(ins):
        fail('duplicate inputs')
    for n, (pins, rows) in nodes.items():
        if n in ins:
            fail('input redriven ' + n)
        if len({r[-1] for r in rows if len(r) == 2}) > 1:
            fail('mixed cover ' + n)
        for p in pins:
            if p not in nodes and p not in ins:
                fail('undriven ' + p)
    return ins, outs, nodes


def table(nodes, n):
    pins, rows = nodes[n]
    k = len(pins)
    if k == 0:
        return [1 if rows == [['1']] else 0]
    on = rows[0][1] if rows else '1'
    tt = [0] * (1 << k)
    for idx in range(1 << k):
        bits = [(idx >> (k - 1 - i)) & 1 for i in range(k)]
        hit = any(all(c == '-' or int(c) == b for c, b in zip(r[0], bits)) for r in rows)
        tt[idx] = int(hit) if on == '1' else int(not hit)
    return tt


def ev(tt, bits):
    idx = 0
    for b in bits:
        idx = (idx << 1) | b
    return tt[idx]


def main():
    blif, meta = sys.argv[1], json.load(open(sys.argv[2]))
    N, T, K, C = meta['N'], meta['T'], meta['K'], meta['C']
    if C != (1 << K) - T or C < 0 or N + C >= (1 << (K + 1)):
        fail('bad offset constants')
    BOUND = N + C
    ONE = '__ONE__'
    ins, outs, nodes = parse(blif)
    if len(ins) != N or len(outs) != 1 or ONE in ins or ONE in nodes:
        fail('interface')
    out = outs[0]
    reach, st = set(), [out]
    while st:
        s = st.pop()
        if s in reach or s not in nodes:
            continue
        reach.add(s); st.extend(nodes[s][0])
    paid = {n for n in reach if len(nodes[n][0]) >= 2}
    if any(len(nodes[n][0]) > 6 for n in reach):
        fail('fanin > 6')
    tts = {}
    frontier = {s: 0 for s in ins}
    used, const_w, dropped = set(), [], []
    assign = 0
    for gi, g in enumerate(meta['groups']):
        gin = [(s, w) for s, w in g['inputs']]
        gout = [(s, w) for s, w in g['outputs']]
        real = [(s, w) for s, w in gin if s != ONE]
        consts = [w for s, w in gin if s == ONE]
        sigs = [s for s, _ in real]
        if len(set(sigs)) != len(sigs) or not 1 <= len(sigs) <= 6:
            fail('group %d inputs' % gi)
        for s, w in real:
            if frontier.get(s) != w:
                fail('group %d input %s not in frontier at weight %d' % (gi, s, w))
        const_w += consts
        for o, u in gout:
            if o not in nodes or nodes[o][0] != sigs or o in used or o in frontier:
                fail('group %d output %s fanins/duplication' % (gi, o))
            tts.setdefault(o, table(nodes, o))
        dw = g.get('dropped_sum_weight')
        if dw is not None:
            if dw >= K or dw in dropped:
                fail('group %d bad dropped weight' % gi)
            dropped.append(dw)
        cval = sum(1 << w for w in consts)
        for v in itertools.product((0, 1), repeat=len(sigs)):
            V = sum(b << w for b, (_, w) in zip(v, real)) + cval
            if V > BOUND:
                continue
            assign += 1
            got = sum(ev(tts[o], v) << u for o, u in gout)
            r = V - got
            if not (r == 0 or (dw is not None and r == (1 << dw))):
                fail('group %d sum mismatch at %s' % (gi, v))
        for s, _ in real:
            del frontier[s]
        for o, u in gout:
            frontier[o] = u
            used.add(o)
    if len(set(const_w)) != len(const_w) or any(w >= K for w in const_w) or sum(1 << w for w in const_w) != C:
        fail('constant offset bits do not sum to C')
    if any(w < K for w in frontier.values()):
        fail('final frontier has weight below K')
    for n in reach:
        tts.setdefault(n, table(nodes, n))
    mf = meta['frontier']
    if sorted(map(tuple, mf)) != sorted(frontier.items()):
        fail('final frontier mismatch')
    region = set()
    st = [out]
    while st:
        s = st.pop()
        if s in frontier or s in region:
            continue
        if s not in nodes:
            fail('compare region reads non-frontier primary input %s' % s)
        if s in used:
            fail('compare region reaches inside a group: %s' % s)
        region.add(s); st.extend(nodes[s][0])
    # every paid reachable node is in a group (used) or region
    stray = paid - used - region
    if stray:
        fail('paid nodes outside groups and region: %d' % len(stray))
    # unused group outputs (dangling) are fine but must not be counted; count reachable paid
    order, seen = [], set()

    def topo(s):
        if s in seen or s in frontier:
            return
        seen.add(s)
        for p in nodes[s][0]:
            topo(p)
        order.append(s)
    sys.setrecursionlimit(100000)
    topo(out)
    fr = sorted(frontier.items(), key=lambda x: x[0])
    names = [s for s, _ in fr]
    ws = [w for _, w in fr]
    if len(names) > 24:
        fail('frontier too large for exhaustive compare check')
    cases = 0
    for v in itertools.product((0, 1), repeat=len(names)):
        S = sum(b << w for b, w in zip(v, ws))
        if S > BOUND:
            continue
        cases += 1
        val = dict(zip(names, v))
        for s in order:
            val[s] = ev(tts[s], [val[p] for p in nodes[s][0]])
        if val[out] != int(S >= (1 << K)):
            fail('compare region wrong at S=%d' % S)
    dep = {}

    def d(s):
        if s not in nodes:
            return 0
        if s not in dep:
            dep[s] = max((d(p) for p in nodes[s][0]), default=0) + (1 if len(nodes[s][0]) >= 2 else 0)
        return dep[s]
    print(json.dumps({'file': blif, 'PASS': True, 'N': N, 'T': T, 'paid_lut6': len(paid),
                      'depth': d(out), 'groups': len(meta['groups']), 'group_assignments': assign,
                      'frontier_bits': len(names), 'compare_nodes': len(region),
                      'compare_cases': cases, 'dropped_weights': sorted(dropped), 'const_weights': sorted(const_w)}))


if __name__ == '__main__':
    main()
