import importlib.util
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'src' / 'tree_viewer.py'


def test_tree_parser_reads_approx_and_column_metadata():
    spec = importlib.util.spec_from_file_location('tree_viewer', MODULE_PATH)
    tree_viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tree_viewer)

    verilog = '''
module test_mul;
    approx_fa_23_105 U0 (IN1[0], IN1[1], 1'b0, w3, w4);
    HalfAdder U1 (IN1[2], IN1[3], w5, w6);
endmodule
'''

    graph = tree_viewer.parse_verilog_tree(verilog, 'test_mul')
    assert any(node['kind'] == 'approx_fa_23_105' for node in graph['nodes'])
    assert any(node['approximate'] is True for node in graph['nodes'])
    assert any(node['column'] == 1 for node in graph['nodes'])
    assert graph['node_count'] >= 2


def test_tree_parser_handles_compact_single_line_module():
    spec = importlib.util.spec_from_file_location('tree_viewer', MODULE_PATH)
    tree_viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tree_viewer)

    verilog = """module test_mul; approx_fa_23_105 U0 (IN1[0], IN1[1], 1'b0, w3, w4); HalfAdder U1 (IN1[2], IN1[3], w5, w6); endmodule"""
    graph = tree_viewer.parse_verilog_tree(verilog, 'test_mul')
    assert graph['node_count'] >= 2
    assert any(node['approximate'] is True for node in graph['nodes'])


def test_tree_parser_builds_stage_snapshots_for_reduction_views():
    spec = importlib.util.spec_from_file_location('tree_viewer', MODULE_PATH)
    tree_viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tree_viewer)

    verilog = '''
module test_mul;
    approx_fa_23_105 U0 (IN1[0], IN1[1], 1'b0, w3, w4);
    HalfAdder U1 (IN1[2], IN1[3], w5, w6);
    approx_fa_23_105 U2 (w3, w5, 1'b0, w7, w8);
endmodule
'''

    graph = tree_viewer.parse_verilog_tree(verilog, 'test_mul')
    assert 'stage_snapshots' in graph
    assert len(graph['stage_snapshots']) >= 2
    assert any(snapshot['approximate'] for snapshot in graph['stage_snapshots'])


def test_tree_parser_includes_ppg_assign_nodes():
    spec = importlib.util.spec_from_file_location('tree_viewer', MODULE_PATH)
    tree_viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tree_viewer)

    verilog = '''
module test_mul;
    assign P0[0] = IN1[0] & IN2[0];
    assign P1[0] = IN1[0] & IN2[1];
    approx_fa_23_105 U0 (P0[0], P1[0], 1'b0, w3, w4);
endmodule
'''

    graph = tree_viewer.parse_verilog_tree(verilog, 'test_mul')
    assert any(node['kind'] == 'PPG' for node in graph['nodes'])
    assert graph['node_count'] >= 3


def test_html_tree_preview_uses_stage_layout_metadata(tmp_path):
    spec = importlib.util.spec_from_file_location('tree_viewer', MODULE_PATH)
    tree_viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tree_viewer)

    verilog = '''
module test_mul;
    assign P0[0] = IN1[0] & IN2[0];
    assign P1[0] = IN1[0] & IN2[1];
    approx_fa_23_105 U0 (P0[0], P1[0], 1'b0, w3, w4);
    HalfAdder U1 (w3, IN1[1], w5, w6);
endmodule
'''
    verilog_path = tmp_path / 'test_mul.v'
    verilog_path.write_text(verilog, encoding='utf-8')
    out_path = tmp_path / 'tree.html'
    generated = tree_viewer.generate_tree_html(str(verilog_path), str(out_path))
    assert generated == str(out_path)
    html_text = out_path.read_text(encoding='utf-8')
    assert 'data-stage="' in html_text
    assert 'data-column="' in html_text
    assert 'tree-surface' in html_text


def test_parser_and_dadda_selector_support_array_and_wallace_modules():
    spec = importlib.util.spec_from_file_location('tree_viewer', MODULE_PATH)
    tree_viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tree_viewer)

    awt_verilog = '''
module AWT(IN0, IN1, IN2, IN3, IN4);
    wire sum0, carry0;
    approx_fa_55_21 U0 (IN0, IN1, IN2, sum0, carry0);
    HalfAdder U1 (sum0, IN3, w1, w2);
endmodule
'''
    graph = tree_viewer.parse_verilog_tree(awt_verilog, 'AWT')
    assert any(node['module_name'] == 'AWT' for node in graph['nodes'])
    assert any(node['approximate'] for node in graph['nodes'])

    aar_verilog = '''
module AAR(IN0, IN1, IN2, IN3, IN4);
    wire sum0, carry0;
    approx_fa_55_21 U0 (IN0, IN1, IN2, sum0, carry0);
    FullAdder U1 (sum0, IN3, IN4, w1, w2);
endmodule
'''
    graph2 = tree_viewer.parse_verilog_tree(aar_verilog, 'AAR')
    assert any(node['module_name'] == 'AAR' for node in graph2['nodes'])
    assert any(node['approximate'] for node in graph2['nodes'])

    dadda_path = ROOT / 'src' / 'DaddaImage.py'
    spec = importlib.util.spec_from_file_location('DaddaImage', dadda_path)
    dadda = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dadda)

    verilog_path = ROOT / 'build' / 'src' / '16_16_U_SP_AWT_RC_M2_COL23_C55_S21_GenMul.v'
    text = verilog_path.read_text(encoding='utf-8', errors='ignore')
    target = dadda.choose_target_module(text)

    assert target in {'AWT', 'ADT'}
    instances, body = dadda.parse_module_instances(text, target)
    assert len(instances) > 200
    assert 'HalfAdder' in body or 'approx_fa_55_21' in body
