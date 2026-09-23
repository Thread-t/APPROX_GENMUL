#!/usr/bin/env python3
"""
FV-LIDAC exhaustive error-combo sweep + equivalence verification (Yosys + ABC Flow).

For a fixed (in1 x in2) Dadda/Ripple-Carry multiplier, this enumerates
approximate full-adder truth tables and, for each one, generates the 
GenMul DEBUG-mode netlist (approx cell + revert cell) and checks it against 
the exact netlist using Yosys -> AIG -> ABC &cec.

IMPORTANT: only approxMethod=2 (pure FA substitution, no truncation) is
checked here. GenMul's revert cell only cancels the FA-substitution error;
it does NOT correct truncation error (approxMethod 1 or 3), so those modes
are never bit-exact and are out of scope for this equivalence sweep.

Requires: the genmul binary already built, `yosys`, and `abc` (or `yosys-abc`) on PATH.
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
    """Runs a command, printing its output live (prefixed [tag]) as it arrives when
    verbose. Returns (returncode, full_text). returncode is None if a timeout happens."""
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


def build_gold(genmul, in1, in2, workdir, timeout, signed_mode=False, verbose=False):
    """Generate the exact netlist and convert it to AIG once. Returns (path, aig_path, topmod)."""
    ppg = 2 if signed_mode else 1
    path = run_genmul(genmul, [ppg, 3, 1, in1, in2], workdir, timeout)
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
               method, timeout, keep_netlists, keep_dir, signed_mode=False, verbose=False):
    """Runs in a worker process. Generates one DEBUG-mode netlist, converts it to AIG, and runs ABC &cec."""
    t0 = time.time()
    ppg = 2 if signed_mode else 1
    tag = f"col{column}_c{cout_mask}_s{sum_mask}"
    
    with tempfile.TemporaryDirectory(prefix="fvlidac_") as tmp:
        try:
            gate_path = run_genmul(
                genmul,
                [ppg, 5, 1, in1, in2, column, cout_mask, sum_mask, method, 1],
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

        # Save files if instructed
        if keep_netlists:
            os.makedirs(keep_dir, exist_ok=True)
            base_name = f"col{column}_c{cout_mask}_s{sum_mask}"
            shutil.copy(gate_path, os.path.join(keep_dir, base_name + ".v"))
            if os.path.exists(gate_aig):
                shutil.copy(gate_aig, os.path.join(keep_dir, base_name + ".aig"))

        # 3. Analyze output mapping
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
    ap.add_argument("--abc", default="yosys-abc", help="Path to ABC binary (Defaults to yosys-abc). Will try 'abc' as a fallback.")
    ap.add_argument("--in1", type=int, default=4)
    ap.add_argument("--in2", type=int, default=4)
    ap.add_argument("--column", type=int, default=None,
                     help="Dadda column to approximate up to (default: max, i.e. whole tree)")
    ap.add_argument("--method", type=int, default=2, choices=[0, 1, 2, 3],
                     help="approxMethod. Only 2 (pure FA substitution) is bit-exact in "
                          "DEBUG mode -- 1 and 3 include truncation, which the revert "
                          "cell cannot undo, so equivalence WILL fail for those.")
    ap.add_argument("--masks", choices=["all", "sample"], default="all",
                     help="'all' = full 256x256=65536 (coutMask,sumMask) space. "
                          "'sample' = a random subset (see --sample-size).")
    ap.add_argument("--sample-size", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--timeout", type=int, default=180, help="per-combo timeout, seconds")
    ap.add_argument("--verbose", action="store_true",
                     help="stream live yosys output for each combo (tagged "
                          "[col<C>_c<cout>_s<sum>]) instead of staying silent.")
    ap.add_argument("--outdir", default="./sweep_results")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--signed", action="store_true",
                     help="Sweep the signed generator (ppg=2, Baugh-Wooley) instead of "
                          "unsigned (ppg=1). Verified equivalent to exact for both square "
                          "and rectangular (nIn1 != nIn2) multipliers.")
    ap.add_argument("--keep-netlists", action="store_true",
                     help="keep every generated DEBUG netlist + AIG (large!). Default: discard.")
    ap.add_argument("--exclude", default="",
                     help="comma-separated cout:sum pairs to skip, e.g. '23:105'")
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

    if args.method != 2:
        print(f"WARNING: --method {args.method} includes truncation error, which the "
              f"revert cell does NOT correct. Equivalence checks below are expected "
              f"to FAIL. Use --method 2 to actually validate the FV-LIDAC mechanism.",
              file=sys.stderr)

    os.makedirs(args.outdir, exist_ok=True)
    workdir = os.path.join(args.outdir, "work")
    os.makedirs(workdir, exist_ok=True)
    keep_dir = os.path.join(args.outdir, "netlists")
    csv_path = os.path.join(args.outdir, "results.csv")

    max_column = args.in1 + args.in2 - 2
    column = args.column if args.column is not None else max_column
    if not (0 <= column <= max_column):
        sys.exit(f"--column must be 0..{max_column} for a {args.in1}x{args.in2} multiplier")

    print(f"Building exact golden netlist and AIG for {args.in1}x{args.in2} "
          f"(Dadda + Ripple-Carry, {'signed' if args.signed else 'unsigned'})...")
    gold_path, gold_aig, topmod = build_gold(
        args.genmul, args.in1, args.in2, workdir, args.timeout, args.signed, args.verbose
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
        print(f"Excluding {sorted(excluded)}: {before - len(combos)} combo(s) removed.")

    done = load_done(csv_path) if args.resume else set()
    todo = [(column, c, s) for (c, s) in combos if (column, c, s) not in done]
    print(f"Total combos: {len(combos)}  Already done (resume): {len(done)}  "
          f"To run: {len(todo)}  Workers: {args.jobs}")

    write_header = not os.path.exists(csv_path)
    fails = []
    n_done = 0
    t_start = time.time()

    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["column", "cout", "sum", "status", "elapsed", "detail"])
        if write_header:
            writer.writeheader()
            f.flush()

        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(check_one, args.genmul, abc_bin, gold_aig, topmod, args.in1, args.in2,
                            col, cout, summ, args.method, args.timeout,
                            args.keep_netlists, keep_dir, args.signed, args.verbose): (col, cout, summ)
                for (col, cout, summ) in todo
            }
            for fut in as_completed(futures):
                result = fut.result()
                writer.writerow(result)
                f.flush()
                n_done += 1
                if result["status"] != "PASS":
                    fails.append(result)
                    print(f"[{n_done}/{len(todo)}] col={result['column']} "
                          f"cout={result['cout']} sum={result['sum']} "
                          f"-> {result['status']}")
                elif n_done % 200 == 0 or n_done == len(todo):
                    elapsed = time.time() - t_start
                    rate = n_done / elapsed if elapsed > 0 else 0
                    remaining = (len(todo) - n_done) / rate if rate > 0 else float("inf")
                    print(f"[{n_done}/{len(todo)}] PASS  "
                          f"({rate:.2f} combos/s, ~{remaining/60:.1f} min remaining)")

    elapsed = time.time() - t_start
    print()
    print(f"=== Done in {elapsed/60:.1f} min ===")
    print(f"Total checked this run: {n_done}")
    print(f"Failures: {len(fails)}")
    if fails:
        print("First failures:")
        for r in fails[:10]:
            print(f"  col={r['column']} cout={r['cout']} sum={r['sum']} status={r['status']}")
        print(f"Full detail in {csv_path}")
        sys.exit(1)
    else:
        print("All checked combos are formally equivalent to the exact design (Verified by ABC &cec).")


if __name__ == "__main__":
    main()