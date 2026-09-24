#!/usr/bin/env python3
"""
FV-LIDAC exhaustive error-combo sweep + equivalence verification (Yosys + ABC Flow).
Supports both Dadda Tree and Array Multiplier architectures.
"""
import argparse
import csv
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

YOSYS_AIG_TEMPLATE = """\
read_verilog {netlist}
synth -top {top}
flatten
aigmap
write_aiger {aig_file}
"""

OUTPUT_FILE_RE = re.compile(r"^Output file: (.+)$", re.MULTILINE)


def run_genmul(genmul, args_list, cwd, timeout):
    r = subprocess.run(
        [genmul] + [str(a) for a in args_list],
        cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"genmul failed (rc={r.returncode}): {r.stderr or r.stdout}")
    m = OUTPUT_FILE_RE.search(r.stdout)
    if not m:
        raise RuntimeError(f"could not find output filename in genmul output: {r.stdout!r}")
    return os.path.join(cwd, m.group(1))


def run_cmd_streaming(cmd_list, stdin_str, cwd, timeout, tag, verbose):
    proc = subprocess.Popen(
        cmd_list, cwd=cwd,
        stdin=subprocess.PIPE if stdin_str is not None else None,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    
    if stdin_str is not None:
        proc.stdin.write(stdin_str)
        proc.stdin.close()

    lines = []
    start = time.time()
    timed_out = False
    for line in proc.stdout:
        lines.append(line)
        if verbose:
            print(f"  [{tag}] {line.rstrip()}", flush=True)
        if timeout and (time.time() - start) > timeout:
            proc.kill()
            timed_out = True
            break
    proc.wait()
    return (None if timed_out else proc.returncode), "".join(lines)


def build_gold(genmul, in1, in2, workdir, timeout, signed_mode=False, arch="array", verbose=False):
    """Generate the exact netlist and convert it to AIG once. Returns (path, aig_path, topmod)."""
    ppg = 2 if signed_mode else 1
    # PPA choice: 1 for Array, 3 for Dadda
    gold_ppa = 1 if arch == "array" else 3
    
    path = run_genmul(genmul, [ppg, gold_ppa, 1, in1, in2], workdir, timeout)
    topmod = f"Mult_{in1}_{in2}"
    
    gold_aig = os.path.join(workdir, f"golden_{topmod}.aig")
    ys_script = YOSYS_AIG_TEMPLATE.format(netlist=path, top=topmod, aig_file=gold_aig)
    
    if verbose:
        print(f"  [gold_aig] starting Yosys AIG generation...", flush=True)
        
    rc, out = run_cmd_streaming(["yosys", "-s", "-"], ys_script, workdir, timeout, "gold_aig", verbose)
    if rc != 0:
        raise RuntimeError(f"Yosys AIG generation failed for golden netlist: {out}")
        
    return path, gold_aig, topmod


def check_one(genmul, abc_bin, gold_aig, topmod, in1, in2, column, cout_mask, sum_mask,
              method, timeout, keep_netlists, keep_dir, signed_mode=False, arch="array", verbose=False):
    """Runs in a worker process. Generates one DEBUG-mode netlist, converts it to AIG, and runs ABC &cec."""
    t0 = time.time()
    ppg = 2 if signed_mode else 1
    # Approx PPA choice: 6 for Approx Array, 5 for Approx Dadda
    approx_ppa = 6 if arch == "array" else 5
    tag = f"col{column}_c{cout_mask}_s{sum_mask}"
    
    with tempfile.TemporaryDirectory(prefix="fvlidac_") as tmp:
        try:
            gate_path = run_genmul(
                genmul,
                [ppg, approx_ppa, 1, in1, in2, column, cout_mask, sum_mask, method, 1],
                tmp, timeout,
            )
        except Exception as e:
            return dict(column=column, cout=cout_mask, sum=sum_mask,
                        status="GENMUL_ERROR", elapsed=time.time() - t0, detail=str(e)[:500])

        gate_aig = os.path.join(tmp, "debug.aig")
        ys_script = YOSYS_AIG_TEMPLATE.format(netlist=gate_path, top=topmod, aig_file=gate_aig)
        
        # 1. Run Yosys to generate DEBUG AIG
        if verbose:
            print(f"  [{tag}] running Yosys to generate AIG...", flush=True)
        rc_ys, out_ys = run_cmd_streaming(["yosys", "-s", "-"], ys_script, tmp, timeout, tag + "_ys", verbose)
        
        if rc_ys is None:
            return dict(column=column, cout=cout_mask, sum=sum_mask,
                        status="TIMEOUT (Yosys)", elapsed=time.time() - t0, detail="yosys timed out")
        if rc_ys != 0:
            return dict(column=column, cout=cout_mask, sum=sum_mask,
                        status="FAIL (Yosys Map)", elapsed=time.time() - t0, detail=out_ys[-800:])

        # 2. Run ABC &cec Equivalent Checking
        if verbose:
            print(f"  [{tag}] running ABC &cec...", flush=True)
        abc_cmd = [abc_bin, "-c", f"&cec {gold_aig} {gate_aig}"]
        rc_abc, out_abc = run_cmd_streaming(abc_cmd, None, tmp, timeout, tag + "_abc", verbose)
        
        if rc_abc is None:
            return dict(column=column, cout=cout_mask, sum=sum_mask,
                        status="TIMEOUT (ABC)", elapsed=time.time() - t0, detail="abc timed out")

        if keep_netlists:
            os.makedirs(keep_dir, exist_ok=True)
            base_name = f"col{column}_c{cout_mask}_s{sum_mask}"
            shutil.copy(gate_path, os.path.join(keep_dir, base_name + ".v"))
            if os.path.exists(gate_aig):
                shutil.copy(gate_aig, os.path.join(keep_dir, base_name + ".aig"))

        status = "PASS" if "Networks are equivalent" in out_abc else "FAIL"
        detail = "" if status == "PASS" else out_abc[-800:]
        
        return dict(column=column, cout=cout_mask, sum=sum_mask, status=status,
                    elapsed=time.time() - t0, detail=detail)


def load_done(csv_path):
    done = set()
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            for row in csv.DictReader(f):
                done.add((int(row["column"]), int(row["cout"]), int(row["sum"])))
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--genmul", default=shutil.which("genmul") or "/opt/genmul/bin/genmul")
    ap.add_argument("--abc", default="yosys-abc", help="Path to ABC binary.")
    ap.add_argument("--in1", type=int, default=16)
    ap.add_argument("--in2", type=int, default=16)
    ap.add_argument("--arch", choices=["array", "dadda"], default="array",
                    help="Architecture to test: 'array' (PPA 1 & 6) or 'dadda' (PPA 3 & 5). Default: array")
    ap.add_argument("--column", type=int, default=None)
    ap.add_argument("--method", type=int, default=2, choices=[0, 1, 2, 3])
    ap.add_argument("--masks", choices=["all", "sample"], default="all")
    ap.add_argument("--sample-size", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--outdir", default="./sweep_results")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--signed", action="store_true")
    ap.add_argument("--keep-netlists", action="store_true")
    ap.add_argument("--exclude", default="")
    args = ap.parse_args()

    if not os.path.exists(args.genmul):
        sys.exit(f"genmul binary not found at {args.genmul} (pass --genmul)")
    if shutil.which("yosys") is None:
        sys.exit("yosys not found on PATH")
        
    abc_bin = args.abc
    if shutil.which(abc_bin) is None:
        if shutil.which("abc") is not None:
            abc_bin = "abc"
        else:
            sys.exit(f"ABC not found at {args.abc} and 'abc' is not in PATH. Please pass --abc.")

    os.makedirs(args.outdir, exist_ok=True)
    workdir = os.path.join(args.outdir, "work")
    os.makedirs(workdir, exist_ok=True)
    keep_dir = os.path.join(args.outdir, "netlists")
    csv_path = os.path.join(args.outdir, "results.csv")

    max_column = args.in1 + args.in2 - 2
    column = args.column if args.column is not None else max_column

    print(f"Building exact golden netlist ({args.arch.upper()}) for {args.in1}x{args.in2} "
          f"({'signed' if args.signed else 'unsigned'})...")
    gold_path, gold_aig, topmod = build_gold(
        args.genmul, args.in1, args.in2, workdir, args.timeout, args.signed, args.arch, args.verbose
    )
    print(f"  gold netlist: {gold_path} \n  gold AIG: {gold_aig} \n  (top module: {topmod})")

    if args.masks == "all":
        combos = [(c, s) for c in range(256) for s in range(256)]
    else:
        rng = random.Random(args.seed)
        pool = [(c, s) for c in range(256) for s in range(256)]
        combos = rng.sample(pool, min(args.sample_size, len(pool)))

    excluded = set()
    if args.exclude:
        for pair in args.exclude.split(","):
            pair = pair.strip()
            if not pair:
                continue
            c_str, s_str = pair.split(":")
            excluded.add((int(c_str), int(s_str)))
    if excluded:
        before = len(combos)
        combos = [cs for cs in combos if cs not in excluded]

    done = load_done(csv_path) if args.resume else set()
    todo = [(column, c, s) for (c, s) in combos if (column, c, s) not in done]
    print(f"Total combos: {len(combos)}  Already done: {len(done)}  To run: {len(todo)}  Workers: {args.jobs}")

    write_header = not os.path.exists(csv_path)
    fails = []
    n_done = 0
    t_start = time.time()

    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["column", "cout", "sum", "status", "elapsed", "detail"])
        if write_header:
            writer.writeheader()
            f.flush()

        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(check_one, args.genmul, abc_bin, gold_aig, topmod, args.in1, args.in2,
                            col, cout, summ, args.method, args.timeout,
                            args.keep_netlists, keep_dir, args.signed, args.arch, args.verbose): (col, cout, summ)
                for (col, cout, summ) in todo
            }
            for fut in as_completed(futures):
                result = fut.result()
                writer.writerow(result)
                f.flush()
                n_done += 1
                if result["status"] != "PASS":
                    fails.append(result)
                    print(f"[{n_done}/{len(todo)}] col={result['column']} cout={result['cout']} sum={result['sum']} -> {result['status']}")
                elif n_done % 200 == 0 or n_done == len(todo):
                    elapsed = time.time() - t_start
                    rate = n_done / elapsed if elapsed > 0 else 0
                    remaining = (len(todo) - n_done) / rate if rate > 0 else float("inf")
                    print(f"[{n_done}/{len(todo)}] PASS ({rate:.2f} combos/s, ~{remaining/60:.1f} min remaining)")

    print(f"\nCompleted in {(time.time() - t_start)/60:.1f} min. Failures: {len(fails)}")

if __name__ == "__main__":
    main()