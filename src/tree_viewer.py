#!/usr/bin/env python3
import argparse
import html
import re
from collections import defaultdict
from pathlib import Path


# ----------------------------------------------------------------------
# Parsing / scheduling / column simulation
# ----------------------------------------------------------------------
# Ported verbatim from dadda_diagram.py (the tool that produces the known-good
# static PNG preview) so the interactive HTML tree is built from the exact
# same module selection, reduction schedule, and per-stage column contents.
# ----------------------------------------------------------------------

EXACT_TYPES = {"FullAdder", "HalfAdder"}

# --- Visual constants, also ported verbatim (as ratios; see UNIT below for
#     how they're scaled into pixels for the SVG) ---
DOT_R = 0.32
DOT_GAP = 0.72
COL_GAP = 1.0
GROUP_GAP = 0.12

DOT_COLOR = "#1a8525"    # Solid green, same for every individual dot
EXACT_COLOR = "#8fa39e"  # Grayish teal box behind exact-adder dot groups
APPROX_COLOR = "#eaa1a1"  # Light red/pink box behind approximate-adder dot groups

LOGIC_MODULE_HINTS = ("AWT", "ADT", "Dadda", "Wallace", "Array")
HELPER_MODULES = {"FullAdder", "FullAdderProp", "HalfAdder", "ConstatntOne", "Counter", "approx_fa_55_21", "U_SP_16_16"}

PIN_RE = re.compile(r"^IN(\d+)\[(\d+)\]$")


def choose_target_module(text):
    module_matches = re.findall(r"\bmodule\s+([A-Za-z0-9_]+)\s*\(.*?\)\s*;", text, re.S)
    if not module_matches:
        raise ValueError("No module definitions found in Verilog.")
    ranked = []
    for name in module_matches:
        if name in HELPER_MODULES:
            continue
        body = re.search(rf"\bmodule\s+{re.escape(name)}\s*\(.*?\)\s*;(.+?)\nendmodule", text, re.S)
        module_body = body.group(1) if body else ""
        inst_count = len(re.findall(r"^\s*\w+\s+\w+\s*\(.*?\)\s*;", module_body, re.M))
        score = 0
        if name in LOGIC_MODULE_HINTS:
            score += 50
        if re.search(r"\b(?:HalfAdder|FullAdder|approx_fa_|Counter)\b", module_body):
            score += 30
        if re.search(r"\bIN\d+\[\d+\]\b", module_body):
            score += 20
        if inst_count > 10:
            score += inst_count
        ranked.append((score, name))
    if not ranked:
        return module_matches[0]
    ranked.sort(reverse=True)
    return ranked[0][1]


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
    return instances, body


def col_of_pin(pin):
    m = PIN_RE.match(pin)
    return int(m.group(1)) if m else None


def build_schedule(instances, module_body):
    stage_of, col_of = {}, {}
    adders = []

    all_inputs = re.findall(r"\bIN(\d+)\[(\d+)\]", module_body)
    for col_str, bit_str in all_inputs:
        pin = f"IN{col_str}[{bit_str}]"
        col_of[pin] = int(col_str)
        stage_of[pin] = 1

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
        return 0, 1

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
            if c is not None:
                cols.append(c)
                stages.append(s)

        if not cols:
            continue

        col = cols[0]
        this_stage = max(stages) if stages else 1

        stage_of[S] = this_stage + 1
        col_of[S] = col
        stage_of[C] = this_stage + 1
        col_of[C] = col + 1

        adders.append({
            "name": name, "type": typ, "is_approx": typ not in EXACT_TYPES,
            "col": col, "stage": this_stage, "inputs": real_ins,
            "sum": S, "carry": C,
        })

    n_stages = max((a["stage"] for a in adders), default=0)
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
        cols[c].sort(key=lambda w: int(re.search(r"\[(\d+)\]", w).group(1)) if "[" in w else 0)

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


def _ordered_blocks(wires, col_adders_here):
    """Groups a column's wires into (adder, consumed_wires) blocks, with any
    leftover (not-yet-consumed) wires as a single free block placed first.
    Ported verbatim from dadda_diagram.py."""
    blocks = []
    used = set()
    for a in col_adders_here:
        group = [w for w in a["inputs"] if w in wires and w not in used]
        if group:
            blocks.append((a, group))
            used.update(group)
    free = [w for w in wires if w not in used]

    result = []
    if free:
        result.append((None, free))
    result.extend(blocks)
    return result


# ----------------------------------------------------------------------
# Graph construction
# ----------------------------------------------------------------------
# graph['nodes'] keeps the flat adder-level shape genmul_gui.py's Tkinter
# "Tree Preview" canvas already relies on (name/kind/column/stage/approximate/
# inputs/outputs). graph['snapshots'] / graph['final_cols'] carry the
# per-stage, per-column wire contents used to build the dot-level SVG below.
# ----------------------------------------------------------------------

def parse_verilog_tree(verilog_text, module_name=None):
    module_name = module_name or choose_target_module(verilog_text)
    instances, module_body = parse_module_instances(verilog_text, module_name)
    adders, stage_of, col_of, _ = build_schedule(instances, module_body)
    snapshots, final_cols, n_stages = simulate_columns(adders, stage_of, col_of)

    all_cols = set(col_of.values())
    min_column = min(all_cols) if all_cols else 0
    max_column = max(all_cols) if all_cols else 0

    nodes = []
    for a in adders:
        nodes.append({
            'kind': a['type'],
            'name': a['name'],
            'inputs': a['inputs'],
            'outputs': [a['sum'], a['carry']],
            'column': a['col'],
            'stage': a['stage'],
            'approximate': a['is_approx'],
            'module_name': module_name,
        })

    graph = {
        'module_name': module_name,
        'min_column': min_column,
        'max_column': max_column,
        'node_count': len(nodes),
        'nodes': nodes,
        'adders': adders,
        'snapshots': snapshots,
        'final_cols': final_cols,
        'n_stages': n_stages,
        'approximate_nodes': [n for n in nodes if n['approximate']],
        'exact_nodes': [n for n in nodes if not n['approximate']],
    }
    return graph


# ----------------------------------------------------------------------
# SVG rendering
# ----------------------------------------------------------------------
# Same stage-by-stage dot/box layout math as dadda_diagram.render_combined
# (same DOT_R/DOT_GAP/COL_GAP/GROUP_GAP ratios, same free-block-first
# ordering, same "box only around adder-consumed dot groups" rule), just
# built directly in an SVG (y grows downward) coordinate space instead of
# a matplotlib (y grows upward, then flipped via ylim) one, and annotated
# with data-* attributes so hovering can show full metadata.
# ----------------------------------------------------------------------

UNIT = 60.0  # pixels per "diagram unit" (dadda_diagram.py's unit was matplotlib inches-ish)
STAGE_GAP = 1.0 * UNIT
LEFT_MARGIN = 4.6 * COL_GAP * UNIT
RIGHT_MARGIN = 1.8 * COL_GAP * UNIT
TOP_MARGIN = 1.4 * UNIT
BOTTOM_MARGIN = 1.0 * UNIT


def _esc(s):
    return html.escape(str(s), quote=True)


def _render_svg_string(graph):
    min_c = graph['min_column']
    max_c = graph['max_column']
    snapshots = graph['snapshots']
    final_cols = graph['final_cols']

    stages_to_draw = list(snapshots)
    if final_cols:
        stages_to_draw.append((graph['n_stages'] + 1, final_cols, []))

    if not stages_to_draw:
        raise ValueError('No reduction stages were found in the generated netlist.')

    dot_r = DOT_R * UNIT
    dot_gap = DOT_GAP * UNIT
    group_gap = GROUP_GAP * UNIT

    def x_of(c):
        return LEFT_MARGIN + (max_c - c) * COL_GAP * UNIT

    svg_body = []
    current_y = TOP_MARGIN

    # Column headers, drawn once above the first stage row.
    for c in range(min_c, max_c + 1):
        x = x_of(c)
        svg_body.append(
            f'<text x="{x:.1f}" y="{current_y - dot_r - 6:.1f}" text-anchor="middle" class="col-label">{c}</text>'
        )

    for i, (s, cols, active) in enumerate(stages_to_draw):
        col_adders = defaultdict(list)
        for a in active:
            col_adders[a['col']].append(a)

        stage_top_y = current_y
        stage_bottom_y = current_y

        for c in range(min_c, max_c + 1):
            wires = cols.get(c, [])
            blocks = _ordered_blocks(wires, col_adders.get(c, []))
            y = stage_top_y

            for bi, (a, group) in enumerate(blocks):
                if bi > 0:
                    y += group_gap

                y0 = y
                x = x_of(c)
                dot_svgs = []
                for w in group:
                    is_grouped = a is not None
                    dot_svgs.append(
                        '<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" '
                        'data-kind="wire" data-wire="{wire}" data-column="{c}" data-stage="{s}" '
                        'data-adder="{adder}" data-adder-kind="{adder_kind}" data-approx="{approx}" '
                        'data-inputs="{inputs}" data-sum="{sum_}" data-carry="{carry}"/>'.format(
                            x=x, y=y, r=dot_r, wire=_esc(w), c=c, s=s,
                            adder=_esc(a['name']) if is_grouped else '',
                            adder_kind=_esc(a['type']) if is_grouped else '',
                            approx='1' if (is_grouped and a['is_approx']) else '0',
                            inputs=_esc(','.join(a['inputs'])) if is_grouped else '',
                            sum_=_esc(a['sum']) if is_grouped else '',
                            carry=_esc(a['carry']) if is_grouped else '',
                        )
                    )
                    y += dot_gap
                y1 = y - dot_gap

                if a is not None:
                    pad = dot_r + 4
                    rx = x - pad
                    ry = y0 - pad
                    rw = 2 * pad
                    rh = (y1 - y0) + 2 * pad
                    color = APPROX_COLOR if a['is_approx'] else EXACT_COLOR
                    # Box first so the dots render on top of it, matching the
                    # static preview's zorder (dots above the group box).
                    svg_body.append(
                        '<rect class="group-box" x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
                        'rx="8" ry="8" fill="{color}" fill-opacity="0.65" stroke="{color}" stroke-width="1" '
                        'data-kind="adder" data-adder="{adder}" data-adder-kind="{adder_kind}" '
                        'data-approx="{approx}" data-inputs="{inputs}" data-sum="{sum_}" data-carry="{carry}" '
                        'data-column="{c}" data-stage="{s}"/>'.format(
                            rx=rx, ry=ry, rw=rw, rh=rh, color=color,
                            adder=_esc(a['name']), adder_kind=_esc(a['type']),
                            approx='1' if a['is_approx'] else '0',
                            inputs=_esc(','.join(a['inputs'])), sum_=_esc(a['sum']), carry=_esc(a['carry']),
                            c=c, s=s,
                        )
                    )
                svg_body.extend(dot_svgs)

                stage_bottom_y = max(stage_bottom_y, y)

        label = f'STAGE {s}' if i < len(stages_to_draw) - 1 else 'RCA STAGE'
        label_x = LEFT_MARGIN - 2.2 * COL_GAP * UNIT
        label_y = (stage_top_y + stage_bottom_y) / 2
        svg_body.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" class="stage-label" '
            f'transform="rotate(-90 {label_x:.1f} {label_y:.1f})">{_esc(label)}</text>'
        )

        current_y = stage_bottom_y + STAGE_GAP
        if i < len(stages_to_draw) - 1:
            line_y = current_y - STAGE_GAP * 0.45
            line_x1 = LEFT_MARGIN - 3.0 * COL_GAP * UNIT
            line_x2 = LEFT_MARGIN + (max_c - min_c) * COL_GAP * UNIT + RIGHT_MARGIN
            svg_body.append(
                f'<line x1="{line_x1:.1f}" y1="{line_y:.1f}" x2="{line_x2:.1f}" y2="{line_y:.1f}" class="stage-sep"/>'
            )

    width = LEFT_MARGIN + (max_c - min_c) * COL_GAP * UNIT + RIGHT_MARGIN
    height = current_y + BOTTOM_MARGIN

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}" '
        'style="width:100%;height:100%;border:1px solid #dfe6ef;border-radius:12px;background:white;">'
        '<defs><style>'
        'text{font-family:Arial,sans-serif;fill:#0f2438}'
        '.col-label{font-size:12px;font-weight:bold}'
        '.stage-label{font-size:12px;font-weight:bold}'
        '.stage-sep{stroke:#8b0000;stroke-width:1;opacity:0.55}'
        f'.dot{{fill:{DOT_COLOR};stroke:none;cursor:pointer}}'
        '.group-box{cursor:pointer}'
        '</style></defs>'
        '<rect width="100%" height="100%" fill="#f6f8fb"/>'
        + ''.join(svg_body) +
        '</svg>'
    )
    return svg


def _render_html(graph, output_path):
    inline_svg = _render_svg_string(graph)

    html_doc = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{html.escape(graph['module_name'])} tree</title>
  <style>
    html, body {{ height: 100%; }}
    body {{ font-family: Arial, sans-serif; background: #eef3f9; margin: 0; display: flex; height: 100vh; }}
    .sidebar {{ width: 340px; background: #fff; border-right: 1px solid #dfe6ef; padding: 16px; box-sizing: border-box; overflow-y: auto; }}
    .main {{ flex: 1; display: flex; flex-direction: column; min-width: 0; }}
    .toolbar {{ display: flex; gap: 12px; align-items: center; background: rgba(255,255,255,0.9); border-bottom: 1px solid #dfe6ef; padding: 12px 16px; }}
    .slider-group {{ display: flex; align-items: center; gap: 8px; min-width: 180px; }}
    .slider-group label {{ font-size: 12px; font-weight: bold; color: #334155; }}
    .viewer {{ flex: 1; overflow: auto; background: #eef3f9; padding: 16px; box-sizing: border-box; touch-action: none; }}
    .tree-surface {{ display: inline-block; position: relative; transform-origin: top left; }}
    .tree-surface svg {{ display: block; transform-origin: top left; will-change: transform; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; color: #fff; margin-right: 8px; }}
    .approx {{ background: #d96868; }} .exact {{ background: #67b16a; }}
    .card {{ background: #f9fbff; border: 1px solid #dfe6ef; border-radius: 12px; padding: 12px; margin-top: 12px; }}
    .card h3 {{ word-break: break-all; }}
  </style>
</head>
<body>
  <div class="sidebar">
    <h2>{html.escape(graph['module_name'])}</h2>
    <p><strong>Approximate adders:</strong> {len(graph['approximate_nodes'])}</p>
    <p><strong>Exact adders:</strong> {len(graph['exact_nodes'])}</p>
    <p><strong>Columns:</strong> {graph['min_column']} to {graph['max_column']}</p>
    <div id="details" class="card">
      <p><em>Select or hover a dot or reduction box to inspect it.</em></p>
    </div>
  </div>
  <div class="main">
    <div class="toolbar">
      <div class="slider-group">
        <label for="panX">Left/Right</label>
        <input id="panX" type="range" min="-1200" max="1200" value="0" />
      </div>
      <div class="slider-group">
        <label for="panY">Up/Down</label>
        <input id="panY" type="range" min="-1000" max="1000" value="0" />
      </div>
      <div class="slider-group">
        <label for="zoom">Zoom</label>
        <input id="zoom" type="range" min="0.5" max="1.8" step="0.05" value="1" />
      </div>
    </div>
    <div class="viewer">
      <div class="tree-surface" id="treeSurface">
        {inline_svg}
      </div>
    </div>
  </div>
  <script>
    const details = document.getElementById('details');
    const defaultText = '<p><em>Select or hover a dot or reduction box to inspect it.</em></p>';
    const panX = document.getElementById('panX');
    const panY = document.getElementById('panY');
    const zoom = document.getElementById('zoom');
    const treeSurface = document.getElementById('treeSurface');
    const svg = treeSurface.querySelector('svg');

    function applyPanZoom() {{
      const x = Number(panX.value);
      const y = Number(panY.value);
      const z = Number(zoom.value);
      const target = svg || treeSurface;
      target.style.transform = 'translate(' + x + 'px, ' + y + 'px) scale(' + z + ')';
    }}

    panX.addEventListener('input', applyPanZoom);
    panY.addEventListener('input', applyPanZoom);
    zoom.addEventListener('input', applyPanZoom);
    applyPanZoom();

    function renderDetails(el) {{
      if (!el) {{ details.innerHTML = defaultText; return; }}
      const kind = el.getAttribute('data-kind');

      if (kind === 'adder') {{
        const approx = el.getAttribute('data-approx') === '1';
        details.innerHTML =
          '<div class="badge ' + (approx ? 'approx' : 'exact') + '">' + (approx ? 'Approx' : 'Exact') + '</div>' +
          '<h3>' + el.getAttribute('data-adder') + '</h3>' +
          '<p><strong>Type:</strong> ' + el.getAttribute('data-adder-kind') + '</p>' +
          '<p><strong>Stage:</strong> ' + el.getAttribute('data-stage') + '</p>' +
          '<p><strong>Column:</strong> ' + el.getAttribute('data-column') + '</p>' +
          '<p><strong>Inputs:</strong> ' + (el.getAttribute('data-inputs') || 'n/a') + '</p>' +
          '<p><strong>Sum:</strong> ' + el.getAttribute('data-sum') + '</p>' +
          '<p><strong>Carry:</strong> ' + el.getAttribute('data-carry') + '</p>';
        return;
      }}

      // Individual wire dot.
      const adderName = el.getAttribute('data-adder');
      if (adderName) {{
        const approx = el.getAttribute('data-approx') === '1';
        details.innerHTML =
          '<div class="badge ' + (approx ? 'approx' : 'exact') + '">' + (approx ? 'Approx' : 'Exact') + '</div>' +
          '<h3>' + el.getAttribute('data-wire') + '</h3>' +
          '<p><strong>Column:</strong> ' + el.getAttribute('data-column') + '</p>' +
          '<p><strong>Stage:</strong> ' + el.getAttribute('data-stage') + '</p>' +
          '<p><strong>Consumed by:</strong> ' + adderName + ' (' + el.getAttribute('data-adder-kind') + ')</p>' +
          '<p><strong>Sibling inputs:</strong> ' + (el.getAttribute('data-inputs') || 'n/a') + '</p>';
      }} else {{
        details.innerHTML =
          '<h3>' + el.getAttribute('data-wire') + '</h3>' +
          '<p><strong>Column:</strong> ' + el.getAttribute('data-column') + '</p>' +
          '<p><strong>Stage:</strong> ' + el.getAttribute('data-stage') + '</p>' +
          '<p><em>Not yet consumed by a reduction cell at this stage.</em></p>';
      }}
    }}

    document.querySelectorAll('.dot, .group-box').forEach((el) => {{
      el.addEventListener('mouseover', () => renderDetails(el));
      el.addEventListener('click', () => renderDetails(el));
    }});
  </script>
</body>
</html>
'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_doc)


def generate_tree_html(verilog_path, output_path=None, module_name=None):
    verilog_path = Path(verilog_path)
    text = verilog_path.read_text(encoding='utf-8', errors='ignore')
    graph = parse_verilog_tree(text, module_name=module_name)
    if output_path is None:
        output_path = verilog_path.with_suffix('.html')

    _render_html(graph, str(output_path))
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description='Generate an interactive HTML tree view from a GenMul Verilog file.')
    parser.add_argument('verilog', help='Path to the generated Verilog file')
    parser.add_argument('-o', '--output', help='Path to the output HTML file')
    parser.add_argument('-m', '--module', help='Optional module name to parse, otherwise the reduction-stage module is auto-selected')
    args = parser.parse_args()
    out = generate_tree_html(args.verilog, args.output, module_name=args.module)
    print(f'Generated tree view: {out}')


if __name__ == '__main__':
    main()