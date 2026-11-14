"""Strict structural readback for the two submitted, positive-cover LUT BLIFs.

Adapted from the separately preserved release structural auditor. This checks
syntax, ordered ports, reachable LUT count and depth, not equivalence.
"""

INPUTS = tuple(f"A[{i}]" for i in range(1001))


def inspect(data):
    rows = data.decode("ascii").replace("\\\n", " ").splitlines()
    ins, outs, nodes, model, current, ended = [], [], {}, None, None, False
    for line in rows:
        cols = line.split("#", 1)[0].split()
        if not cols:
            continue
        op = cols[0]
        if ended:
            raise ValueError("content after .end")
        if op == ".model":
            if model is not None or len(cols) != 2:
                raise ValueError("model")
            model, current = cols[1], None
        elif op == ".inputs":
            ins += cols[1:]
            current = None
        elif op == ".outputs":
            outs += cols[1:]
            current = None
        elif op == ".names":
            pins, out = cols[1:-1], cols[-1]
            if out in nodes or out in ins or len(pins) < 2 or len(pins) > 6 or len(set(pins)) != len(pins):
                raise ValueError("invalid LUT " + out)
            nodes[out] = (pins, [])
            current = out
        elif op == ".end":
            if len(cols) != 1:
                raise ValueError("end")
            ended, current = True, None
        elif op.startswith("."):
            raise ValueError("unsupported directive " + op)
        else:
            if current is None:
                raise ValueError("cube outside LUT")
            pins, covers = nodes[current]
            if len(cols) != 2 or len(cols[0]) != len(pins) or set(cols[0]) - set("01-") or cols[1] != "1":
                raise ValueError("invalid LUT cover")
            covers.append(cols[0])
    if not ended or model != "top" or tuple(ins) != INPUTS or outs != ["maj"]:
        raise ValueError("interface/model")
    for name, (pins, _) in nodes.items():
        if any(p not in nodes and p not in ins for p in pins):
            raise ValueError("undriven fanin " + name)
    depth, active = {}, set()

    def visit(name):
        if name in ins:
            return 0
        if name in depth:
            return depth[name]
        if name in active or name not in nodes:
            raise ValueError("cycle or undriven output")
        active.add(name)
        depth[name] = 1 + max(visit(p) for p in nodes[name][0])
        active.remove(name)
        return depth[name]

    actual_depth = visit("maj")
    if len(depth) != len(nodes):
        raise ValueError("unreachable LUT")
    return {"lut6": len(nodes), "depth": actual_depth, "inputs": len(ins), "outputs": len(outs)}
