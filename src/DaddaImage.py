#!/usr/bin/env python3
"""
dadda_diagram.py
-----------------
Reconstructs and draws a stage-by-stage dot diagram of a GenMul-generated
Dadda / approximate-Dadda partial-product reduction tree, straight from the
Verilog source -- no other input needed.

USAGE
    python3 dadda_diagram.py INPUT.v [-o OUTPUT.png] [-m MODULE_NAME]

    INPUT.v        The Verilog file produced by GenMul (contains a module,
                    default name "ADT", that instantiates FullAdder /
                    HalfAdder / approx_fa_* compressors).
    -o OUTPUT.png  Where to save the diagram (default: <input>_dadda.png).
    -m MODULE_NAME Name of the reduction-tree module to parse, if it isn't
                    called "ADT" (default: "ADT").

WHAT IT ASSUMES (true for all GenMul U_SP + ADT + RC outputs)
  * Primary inputs are named IN<col>[<bit>] where <col> is directly the
    column / weight index -- no separate column inference is required.
  * Instances appear in the file in dependency order (every wire is used
    only after the line that defines it).
  * Every compressor instance is a 2-input (HalfAdder-style: X,Y,S,C) or
    3-input (FullAdder-style: X,Y,Z,S,C/Cout) adder/compressor.
  * Any instantiated module type other than "FullAdder" / "HalfAdder" is
    treated as an *approximate* compressor (this covers approx_fa_31_0,
    approx_fa_80_47, approx_fa_4_127, or any other name GenMul emits --
    nothing is hardcoded about the specific approximate module name).

OUTPUT
  A PNG with one panel per reduction stage (dots + boxed groups showing
  which bits get compressed together that stage, green = exact, orange =
  approximate) plus a final panel showing the column heights handed off
  to the ripple-carry / final adder.
"""

import argparse
import re
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

EXACT_TYPES = {"FullAdder", "HalfAdder"}

# ----------------------------------------------------------------------
# 1. Parsing
# ----------------------------------------------------------------------

def parse_module_instances(text, module_name):
    """Return a list of (module_type, instance_name, [args...]) for every
    compressor instance found inside `module <module_name> ( ... ); ... endmodule`.
    Only instances whose module_type looks like an adder/compressor (2 or 3
    inputs + 1 or 2 outputs, i.e. total 4-5 ports) are kept; anything else
    inside the module (unlikely, but just in case) is ignored.
    """
    m = re.search(rf"\bmodule\s+{re.escape(module_name)}\s*\(.*?\);(.*?)\nendmodule",
                  text, re.S)
    if not m:
        raise ValueError(
            f"Could not find 'module {module_name}( ... ); ... endmodule' in the file. "
            f"Pass -m <name> if your reduction-tree module has a different name."
        )
    body = m.group(1)

    # Matches: <ModuleType> <instance_name> ( arg0, arg1, ... );
    inst_re = re.compile(r"^\s*(\w+)\s+(\w+)\s*\(([^;]*?)\)\s*;", re.M)

    instances = []
    for mm in inst_re.finditer(body):
        typ, name, argstr = mm.groups()
        if typ in ("wire", "input", "output", "assign", "reg"):
            continue
        args = [a.strip() for a in argstr.split(",")]
        if len(args) not in (4, 5):
            # not a 2-input (X,Y,S,C) or 3-input (X,Y,Z,S,C) compressor -> skip
            continue
        instances.append((typ, name, args))
    return instances


PIN_RE = re.compile(r"^IN(\d+)\[(\d+)\]$")


def col_of_pin(pin):
    m = PIN_RE.match(pin)
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------------
# 2. Build the reduction schedule
# ----------------------------------------------------------------------

def build_schedule(instances):
    """
    For every wire, compute:
      stage_of[wire]: earliest stage at which the dot is PRESENT/available
      col_of[wire]:   its column (bit-weight)
    For every instance, compute the stage in which it fires and which
    exact inputs/outputs it touches.
    """
    stage_of, col_of = {}, {}
    adders = []

    def get_col_stage(pin):
        if pin in ("1'b0", "1'b1", "0", "1"):
            return None, None
        if pin in col_of:
            return col_of[pin], stage_of[pin]
        c = col_of_pin(pin)
        if c is not None:
            col_of[pin] = c
            stage_of[pin] = 1
            return c, 1
        raise KeyError(
            f"Wire '{pin}' used before it was defined -- the instances in this "
            f"file may not be in dependency order, which this tool assumes."
        )

    for typ, name, args in instances:
        if len(args) == 4:       # HalfAdder-style: X, Y, S, C
            X, Y, S, C = args
            ins = [X, Y]
        else:                    # FullAdder-style: X, Y, Z, S, C
            X, Y, Z, S, C = args
            ins = [X, Y, Z]

        real_ins = [p for p in ins if p not in ("1'b0", "1'b1", "0", "1")]
        if not real_ins:
            continue
        cols, stages = [], []
        for p in real_ins:
            c, s = get_col_stage(p)
            cols.append(c)
            stages.append(s)

        col = cols[0]
        this_stage = max(stages)

        stage_of[S] = this_stage + 1
        col_of[S] = col
        stage_of[C] = this_stage + 1
        col_of[C] = col + 1

        adders.append({
            "name": name,
            "type": typ,
            "is_approx": typ not in EXACT_TYPES,
            "col": col,
            "stage": this_stage,
            "inputs": real_ins,
            "sum": S,
            "carry": C,
        })

    if not adders:
        raise ValueError("No compressor instances found -- nothing to draw.")

    n_stages = max(a["stage"] for a in adders)
    return adders, stage_of, col_of, n_stages


def simulate_columns(adders, stage_of, col_of):
    """Walk stage by stage, returning per-stage column snapshots plus the
    final column contents handed to the next adder stage (RCA etc.)."""
    produced_wires = set()
    for a in adders:
        produced_wires.add(a["sum"])
        produced_wires.add(a["carry"])

    cols = defaultdict(list)
    for wire, s in stage_of.items():
        if s == 1 and wire not in produced_wires:
            cols[col_of[wire]].append(wire)
    for c in cols:
        cols[c].sort(key=lambda w: int(re.search(r"\[(\d+)\]", w).group(1)))

    adders_by_stage = defaultdict(list)
    for a in adders:
        adders_by_stage[a["stage"]].append(a)

    n_stages = max(adders_by_stage.keys())
    snapshots = []
    for s in range(1, n_stages + 1):
        snap = {c: list(w) for c, w in cols.items()}
        snapshots.append((s, snap, adders_by_stage[s]))
        for a in adders_by_stage[s]:
            for w in a["inputs"]:
                if w in cols[a["col"]]:
                    cols[a["col"]].remove(w)
            cols[a["col"]].append(a["sum"])
            cols[a["col"] + 1].append(a["carry"])

    final_cols = {c: list(w) for c, w in cols.items()}
    return snapshots, final_cols, n_stages


# ----------------------------------------------------------------------
# 3. Rendering
# ----------------------------------------------------------------------

DOT_R = 0.34
DOT_GAP = 1.05
COL_GAP = 1.2
GROUP_GAP = 0.4   # extra vertical space inserted between one group/free-block and the next

EXACT_COLOR = "#6fae6f"
APPROX_COLOR = "#e8a33d"


def _ordered_blocks(wires, col_adders_here):
    """Split a column's dot list into ordered blocks: one block per compressor
    that fires on this column this stage (its exact input wires, and only
    those), followed by one trailing block of the untouched/free dots.
    This guarantees a compressor's box can never enclose a dot that isn't
    actually one of its inputs, regardless of the dots' original list order.
    """
    blocks = []  # list of (adder_or_None, [wires])
    used = set()
    for a in col_adders_here:
        group = [w for w in a["inputs"] if w in wires and w not in used]
        if group:
            blocks.append((a, group))
            used.update(group)
    free = [w for w in wires if w not in used]
    if free:
        blocks.append((None, free))
    return blocks


def draw_stage(ax, cols, active_adders, title, min_c, max_c):
    col_adders = defaultdict(list)
    for a in active_adders:
        col_adders[a["col"]].append(a)

    # Assign each wire a y-position, with a small gap between blocks so a
    # group's box/label never overlaps its neighbours.
    pos = {}          # wire -> (col, y)
    col_top_y = {}     # column -> highest y used (for axis limits)
    box_specs = []     # (adder, x, y0, y1) to draw after all dots are placed

    for c, wires in cols.items():
        blocks = _ordered_blocks(wires, col_adders.get(c, []))
        y = 0.0
        for bi, (a, group) in enumerate(blocks):
            if bi > 0:
                y += GROUP_GAP
            y0 = y
            for w in group:
                pos[w] = (c, y)
                y += DOT_GAP
            y1 = y - DOT_GAP
            if a is not None:
                box_specs.append((a, c, y0, y1))
        col_top_y[c] = y

    for c, wires in cols.items():
        for w in wires:
            _, y = pos[w]
            x = (c - min_c) * COL_GAP
            ax.add_patch(patches.Circle((x, y), DOT_R, facecolor="white",
                                         edgecolor="black", linewidth=0.8, zorder=3))

    for a, c, y0, y1 in box_specs:
        x = (c - min_c) * COL_GAP
        color = APPROX_COLOR if a["is_approx"] else EXACT_COLOR
        n_in = len(a["inputs"])
        label = ("HA" if n_in == 2 else "FA") + ("*" if a["is_approx"] else "")
        pad = DOT_R + 0.12
        rect = patches.FancyBboxPatch(
            (x - pad, y0 - pad), 2 * pad, (y1 - y0) + 2 * pad,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.3, edgecolor=color, facecolor=color, alpha=0.25, zorder=2
        )
        ax.add_patch(rect)
        ax.text(x, y1 + pad + 0.15, label, ha="center", va="bottom",
                 fontsize=6, color=color, fontweight="bold", zorder=4)

    max_h = max(col_top_y.values(), default=1.0)
    ax.set_xlim(-1, (max_c - min_c) * COL_GAP + 1)
    ax.set_ylim(-0.8, max_h + 1.0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9, loc="left")


def _stage_panels(snapshots, final_cols):
    all_cols = set()
    for _, cols, _ in snapshots:
        all_cols |= set(cols.keys())
    all_cols |= set(final_cols.keys())
    min_c, max_c = min(all_cols), max(all_cols)

    panel_specs = []  # (title, cols, active)
    for s, cols, active in snapshots:
        n_approx = sum(1 for a in active if a["is_approx"])
        n_exact = len(active) - n_approx
        title = f"Stage {s}  ({n_exact} exact, {n_approx} approximate compressors)"
        panel_specs.append((title, cols, active))
    panel_specs.append(("Into final adder stage (post-Dadda column vectors)", final_cols, []))
    return panel_specs, min_c, max_c


# ----------------------------------------------------------------------
# 3b. Graphviz (.dot) export -- vector output, immune to raster scaling
# ----------------------------------------------------------------------

DOT_X_STEP = 0.55   # inches between columns
DOT_Y_STEP = 0.45   # inches between rows within a column
DOT_GROUP_GAP = 0.20  # extra inches between one group/free-block and the next
NODE_DIAM = 0.32    # inches


def _gv_id(wire):
    return '"' + wire.replace('"', '\\"') + '"'


def write_stage_dot(cols, active_adders, min_c, max_c, title, path):
    """Write one Graphviz file for a single stage. Uses engine=neato with
    pinned node positions (pos="x,y!") and no edges at all -- the only thing
    being drawn is dots (nodes) and grouping boxes (clusters), so there is
    nothing for a layout engine to compute or get wrong. Render with:
        neato -n2 -Tsvg stage.dot -o stage.svg
        neato -n2 -Tpdf stage.dot -o stage.pdf
    Both are vector formats: they stay pixel-perfect at any zoom or print
    size, which is the main advantage over the PNG output for large trees.
    """
    col_adders = defaultdict(list)
    for a in active_adders:
        col_adders[a["col"]].append(a)

    lines = []
    lines.append("graph dadda_stage {")
    lines.append('  layout=neato;')
    lines.append('  outputorder=edgesfirst;')
    lines.append(f'  label="{title}";')
    lines.append('  labelloc=t; fontsize=16; fontname="Helvetica";')
    lines.append('  node [shape=circle, style=filled, fillcolor=white, color=black, '
                  f'fixedsize=true, width={NODE_DIAM}, height={NODE_DIAM}, label=""];')

    cluster_i = 0
    for c, wires in cols.items():
        blocks = _ordered_blocks(wires, col_adders.get(c, []))
        y = 0.0
        for bi, (a, group) in enumerate(blocks):
            if bi > 0:
                y += DOT_GROUP_GAP
            x = (c - min_c) * DOT_X_STEP
            node_ys = []
            for w in group:
                lines.append(f'  {_gv_id(w)} [pos="{x:.3f},{y:.3f}!"];')
                node_ys.append(y)
                y += DOT_Y_STEP
            if a is not None:
                color = APPROX_COLOR if a["is_approx"] else EXACT_COLOR
                n_in = len(a["inputs"])
                label = ("HA" if n_in == 2 else "FA") + ("*" if a["is_approx"] else "")
                lines.append(f"  subgraph cluster_{cluster_i} {{")
                lines.append(f'    style=filled; color="{color}"; fillcolor="{color}30";')
                lines.append(f'    label="{label}"; fontsize=9; fontcolor="{color}"; '
                              f'labeljust=c; labelloc=t;')
                for w in group:
                    lines.append(f"    {_gv_id(w)};")
                lines.append("  }")
                cluster_i += 1

    lines.append("}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_dot_files(snapshots, final_cols, min_c, max_c, out_prefix):
    panel_specs, _, _ = None, None, None  # placeholder, filled below
    panel_specs = []
    for s, cols, active in snapshots:
        n_approx = sum(1 for a in active if a["is_approx"])
        n_exact = len(active) - n_approx
        title = f"Stage {s} ({n_exact} exact, {n_approx} approximate)"
        panel_specs.append((f"stage{s:02d}", title, cols, active))
    panel_specs.append(("final", "Into final adder stage", final_cols, []))

    saved = []
    for name, title, cols, active in panel_specs:
        path = f"{out_prefix}_{name}.dot"
        write_stage_dot(cols, active, min_c, max_c, title, path)
        saved.append(path)
    return saved


def render(snapshots, final_cols, n_stages, out_path, header, split=False):
    all_cols = set()
    for _, cols, _ in snapshots:
        all_cols |= set(cols.keys())
    all_cols |= set(final_cols.keys())
    min_c, max_c = min(all_cols), max(all_cols)

    panel_specs = []  # (title, cols, active)
    for s, cols, active in snapshots:
        n_approx = sum(1 for a in active if a["is_approx"])
        n_exact = len(active) - n_approx
        title = f"Stage {s}  ({n_exact} exact, {n_approx} approximate compressors)"
        panel_specs.append((title, cols, active))
    panel_specs.append(("Into final adder stage (post-Dadda column vectors)", final_cols, []))

    if split:
        base = out_path.rsplit(".", 1)[0]
        ext = out_path.rsplit(".", 1)[1] if "." in out_path else "png"
        saved = []
        for i, (title, cols, active) in enumerate(panel_specs, start=1):
            fig, ax = plt.subplots(figsize=(16, 3.4))
            draw_stage(ax, cols, active, title, min_c, max_c)
            fig.suptitle(header if i == 1 else "", fontsize=11, y=0.99)
            fig.tight_layout(rect=[0, 0, 1, 0.95] if i == 1 else None)
            path = f"{base}_stage{i:02d}.{ext}" if i <= n_stages else f"{base}_final.{ext}"
            fig.savefig(path, dpi=260, bbox_inches="tight")
            plt.close(fig)
            saved.append(path)
        return saved

    n_panels = n_stages + 1
    fig, axes = plt.subplots(n_panels, 1, figsize=(16, 3.0 * n_panels))
    if n_panels == 1:
        axes = [axes]

    for (title, cols, active), ax in zip(panel_specs, axes):
        draw_stage(ax, cols, active, title, min_c, max_c)

    fig.suptitle(header, fontsize=13, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=260, bbox_inches="tight")
    plt.close(fig)
    return [out_path]


# ----------------------------------------------------------------------
# 4. CLI
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Draw a Dadda-tree dot diagram from GenMul Verilog.")
    ap.add_argument("verilog", help="Path to the GenMul-generated .v file")
    ap.add_argument("-o", "--output", default=None, help="Output PNG path")
    ap.add_argument("-m", "--module", default="ADT",
                     help="Name of the reduction-tree module to parse (default: ADT)")
    ap.add_argument("--split", action="store_true",
                     help="Save each stage as its own PNG instead of one tall combined image "
                          "(recommended if you'll be viewing/sharing at small sizes)")
    args = ap.parse_args()

    text = open(args.verilog).read()
    instances = parse_module_instances(text, args.module)
    adders, stage_of, col_of, n_stages = build_schedule(instances)
    snapshots, final_cols, n_stages = simulate_columns(adders, stage_of, col_of)

    n_approx_total = sum(1 for a in adders if a["is_approx"])
    n_exact_total = len(adders) - n_approx_total
    approx_types = sorted({a["type"] for a in adders if a["is_approx"]})

    out_path = args.output or (args.verilog.rsplit(".", 1)[0] + "_dadda.png")
    header = (f"Reconstructed reduction tree from '{args.module}' module "
              f"({len(adders)} compressors, {n_stages} stages, "
              f"{n_exact_total} exact / {n_approx_total} approximate)")

    saved = render(snapshots, final_cols, n_stages, out_path, header, split=args.split)

    print(f"Parsed {len(instances)} compressor instances from module '{args.module}'.")
    print(f"  Exact compressors      : {n_exact_total}")
    print(f"  Approximate compressors: {n_approx_total}"
          + (f"  (types: {', '.join(approx_types)})" if approx_types else ""))
    print(f"Reduction depth: {n_stages} stages")
    if len(saved) > 1:
        print(f"Saved {len(saved)} per-stage diagrams:")
        for p in saved:
            print(f"  {p}")
    else:
        print(f"Saved diagram to: {saved[0]}")


if __name__ == "__main__":
    main()