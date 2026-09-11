#!/usr/bin/env python3
"""
dadda_diagram.py
-----------------
Reconstructs and draws a stage-by-stage dot diagram of a GenMul-generated
Dadda / approximate-Dadda partial-product reduction tree, formatting the output
to exactly match standard continuous hardware visualization plots.
"""

import argparse
import re
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as lines

EXACT_TYPES = {"FullAdder", "HalfAdder"}

# --- Visual Styling to match reference diagram ---
DOT_R = 0.30
DOT_GAP = 0.95
COL_GAP = 1.05
GROUP_GAP = 0.2

DOT_COLOR = "#1a8525"    # Solid Green
EXACT_COLOR = "#8fa39e"  # Grayish teal
APPROX_COLOR = "#eaa1a1" # Light red/pink

# ----------------------------------------------------------------------
# 1. Parsing
# ----------------------------------------------------------------------
def parse_module_instances(text, module_name):
    m = re.search(rf"\bmodule\s+{re.escape(module_name)}\s*\(.*?\);(.*?)\nendmodule", text, re.S)
    if not m:
        raise ValueError(f"Could not find 'module {module_name}'.")
    body = m.group(1)
    inst_re = re.compile(r"^\s*(\w+)\s+(\w+)\s*\(([^;]*?)\)\s*;", re.M)

    instances = []
    for mm in inst_re.finditer(body):
        typ, name, argstr = mm.groups()
        if typ in ("wire", "input", "output", "assign", "reg"):
            continue
        args = [a.strip() for a in argstr.split(",")]
        if len(args) not in (4, 5):
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
        raise KeyError(f"Wire '{pin}' used before defined.")

    for typ, name, args in instances:
        if len(args) == 4:
            X, Y, S, C = args
            ins = [X, Y]
        else:
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
            "name": name, "type": typ, "is_approx": typ not in EXACT_TYPES,
            "col": col, "stage": this_stage, "inputs": real_ins,
            "sum": S, "carry": C,
        })

    n_stages = max(a["stage"] for a in adders) if adders else 0
    return adders, stage_of, col_of, n_stages

def simulate_columns(adders, stage_of, col_of):
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

    n_stages = max(adders_by_stage.keys()) if adders_by_stage else 0
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
# 3. Rendering (Overhauled for continuous visual layout)
# ----------------------------------------------------------------------
def _ordered_blocks(wires, col_adders_here):
    blocks = []
    used = set()
    for a in col_adders_here:
        group = [w for w in a["inputs"] if w in wires and w not in used]
        if group:
            blocks.append((a, group))
            used.update(group)
    free = [w for w in wires if w not in used]
    
    result = []
    # Place uncompressed (free) dots at the top of the column block 
    if free:
        result.append((None, free))
    result.extend(blocks)
    return result

def render_combined(snapshots, final_cols, out_path, min_c, max_c):
    stages_to_draw = list(snapshots)
    if final_cols:
        stages_to_draw.append((len(snapshots) + 1, final_cols, []))
        
    fig_width = max(8, (max_c - min_c + 4) * 0.35)
    fig_height = max(4, len(stages_to_draw) * 2.2)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    
    current_y = 0.0
    
    # Draw Top Column Indices
    for c in range(min_c, max_c + 1):
        x = (max_c - c) * COL_GAP
        ax.text(x, current_y + DOT_R + 0.3, str(c), ha="center", va="bottom", 
                fontsize=8, fontweight="bold", color="black")
    
    for i, (s, cols, active) in enumerate(stages_to_draw):
        col_adders = defaultdict(list)
        for a in active:
            col_adders[a["col"]].append(a)
            
        stage_top_y = current_y
        stage_bottom_y = current_y
        
        for c, wires in cols.items():
            blocks = _ordered_blocks(wires, col_adders.get(c, []))
            y = stage_top_y
            
            for bi, (a, group) in enumerate(blocks):
                if bi > 0:
                    y -= GROUP_GAP
                    
                y0 = y
                for w in group:
                    x = (max_c - c) * COL_GAP
                    ax.add_patch(patches.Circle((x, y), DOT_R, facecolor=DOT_COLOR, 
                                                edgecolor="none", zorder=3))
                    y -= DOT_GAP
                y1 = y + DOT_GAP # Adjust back to last drawn dot
                
                if a is not None:
                    x = (max_c - c) * COL_GAP
                    color = APPROX_COLOR if a["is_approx"] else EXACT_COLOR
                    pad = DOT_R + 0.1
                    rect = patches.FancyBboxPatch(
                        (x - pad, y1 - pad), 2 * pad, (y0 - y1) + 2 * pad,
                        boxstyle="round,pad=0.02,rounding_size=0.1",
                        linewidth=0.5, edgecolor=color, facecolor=color, alpha=0.6, zorder=2
                    )
                    ax.add_patch(rect)
                    
                stage_bottom_y = min(stage_bottom_y, y)
        
        # Draw Stage Label on Left side
        label = f"STAGE {s}" if i < len(stages_to_draw) - 1 else f"RCA STAGE {s}"
        label_x = -2.5 * COL_GAP
        label_y = (stage_top_y + stage_bottom_y + DOT_GAP) / 2
        ax.text(label_x, label_y, label, rotation=90, ha="center", va="center", 
                fontsize=8, fontweight="bold")
        
        # Advance Y and Draw Separator
        current_y = stage_bottom_y - 1.2
        if i < len(stages_to_draw) - 1:
            line_y = current_y + 0.6
            line = lines.Line2D([-3.5 * COL_GAP, (max_c - min_c + 1) * COL_GAP], 
                                [line_y, line_y], lw=0.8, color="#8b0000", alpha=0.6)
            ax.add_line(line)
            
    # Calculate limits to tightly bound the drawing
    ax.set_xlim(-4 * COL_GAP, (max_c - min_c + 1.5) * COL_GAP)
    ax.set_ylim(current_y, 1.5)
    ax.set_aspect("equal")
    ax.axis("off")
    
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return [out_path]

# ----------------------------------------------------------------------
# 4. CLI
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("verilog", help="Path to the GenMul-generated .v file")
    ap.add_argument("-o", "--output", default=None, help="Output PNG path")
    ap.add_argument("-m", "--module", default="ADT", help="Target module name")
    args = ap.parse_args()

    text = open(args.verilog).read()
    instances = parse_module_instances(text, args.module)
    adders, stage_of, col_of, n_stages = build_schedule(instances)
    snapshots, final_cols, n_stages = simulate_columns(adders, stage_of, col_of)

    all_cols = set()
    for _, cols, _ in snapshots:
        all_cols |= set(cols.keys())
    all_cols |= set(final_cols.keys())
    min_c, max_c = min(all_cols), max(all_cols)

    out_path = args.output or (args.verilog.rsplit(".", 1)[0] + "_dadda.png")
    saved = render_combined(snapshots, final_cols, out_path, min_c, max_c)

    print(f"Generated unified Dadda tree diagram: {saved[0]}")

if __name__ == "__main__":
    main()