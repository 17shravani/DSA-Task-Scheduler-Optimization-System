# -*- coding: utf-8 -*-
"""
Task Scheduler Optimization System
====================================
Main CLI Entry Point

Usage:
  python main.py                         # greedy scheduler, default settings
  python main.py --engine cpsat          # CP-SAT optimal solver
  python main.py --engine greedy --horizon 48
  python main.py --engine cpsat --objective makespan
  python main.py --compare               # run both and compare
  python main.py --export                # save CSV + text report
  python main.py --demo                  # show full simulation walkthrough
"""

import argparse
import os
import sys
import io

# Fix Windows terminal encoding so Unicode prints work correctly
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models import load_tasks, load_resources, validate_all_tasks
from src.greedy import greedy_schedule, topological_sort_by_priority
from src.metrics import compute_kpis, compare_plans
from src.reporter import (
    print_schedule_table,
    print_kpis,
    print_comparison,
    print_ascii_gantt,
    export_csv,
    export_text_report,
)


# ────────────────────────────────────────────────────────────
# Paths
# ────────────────────────────────────────────────────────────
DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")
TASKS_CSV  = os.path.join(DATA_DIR, "tasks.csv")
RES_CSV    = os.path.join(DATA_DIR, "resources.csv")


# ────────────────────────────────────────────────────────────
# Banner
# ────────────────────────────────────────────────────────────
BANNER = """
================================================================
  TASK SCHEDULER OPTIMIZATION SYSTEM  v1.0
  DSA Project  |  Greedy + CP-SAT + What-If Dashboard
================================================================
  [Concepts] Priority Queue | Greedy | CP-SAT | DAG Topo Sort
================================================================
"""


# ────────────────────────────────────────────────────────────
# Demo / Simulation walkthrough
# ────────────────────────────────────────────────────────────
def run_demo(tasks, resources, horizon, export):
    """Full step-by-step simulation walkthrough."""

    print("\n" + "#" * 62)
    print("  VIRTUAL SIMULATION -- FULL WALKTHROUGH")
    print("#" * 62)

    # Stage 1: Raw Input
    print("\n[STAGE 1] RAW TASK INPUT")
    print("-" * 62)
    print(f"  {'ID':<6} {'Name':<28} {'Dur':>4} {'DL':>4} {'Prio':>5} {'Skill':<10} {'Profit':>7} {'Deps'}")
    print("-" * 62)
    for t in tasks:
        deps_str = "|".join(t.depends_on) if t.depends_on else "--"
        print(f"  {t.task_id:<6} {t.task_name:<28} {t.duration_h:>3}h {t.deadline_h:>3}h "
              f"{t.priority:>5}  {t.skill:<10} {t.profit:>7}  {deps_str}")

    # Stage 2: Validation
    print("\n[STAGE 2] TASK VALIDATION")
    print("-" * 62)
    valid = validate_all_tasks(tasks)
    if valid:
        print("  All tasks passed validation  [OK]")
    else:
        print("  WARNING: Validation errors found -- fix before proceeding")

    # Stage 3: Topological Sort
    print("\n[STAGE 3] PRIORITY QUEUE + TOPOLOGICAL SORT (Kahn's BFS)")
    print("-" * 62)
    topo_order = topological_sort_by_priority(tasks)
    print("  Processing order (respects dependencies + priority):")
    task_map = {t.task_id: t for t in tasks}
    for i, tid in enumerate(topo_order, 1):
        t = task_map[tid]
        print(f"    {i:2}. {tid}  -- {t.task_name:<28}  prio={t.priority}  deadline={t.deadline_h}h")

    # Stage 4: Greedy Schedule
    print("\n[STAGE 4] GREEDY SCHEDULING ALGORITHM")
    print("-" * 62)
    greedy_plan = greedy_schedule(tasks, resources, horizon=horizon)
    print_schedule_table(greedy_plan, title="GREEDY SCHEDULE")
    greedy_kpis = compute_kpis(greedy_plan)
    print_kpis(greedy_kpis, label="GREEDY")

    # Stage 5: ASCII Gantt
    print("\n[STAGE 5] EXECUTION TIMELINE (ASCII GANTT CHART)")
    print_ascii_gantt(greedy_plan, horizon=horizon, scale=2)

    # Stage 6: CP-SAT (if available)
    cpsat_plan = greedy_plan
    cpsat_kpis = greedy_kpis

    try:
        from src.cpsat_solver import solve_cpsat, HAS_ORTOOLS
        if HAS_ORTOOLS:
            print("\n[STAGE 6] CP-SAT OPTIMAL SOLVER (OR-Tools)")
            print("-" * 62)
            print("  Running CP-SAT solver ... (up to 15s)")
            status, cpsat_plan = solve_cpsat(tasks, resources, horizon=horizon)
            print(f"  Solver status: {status}")
            print_schedule_table(cpsat_plan, title=f"CP-SAT SCHEDULE ({status})")
            cpsat_kpis = compute_kpis(cpsat_plan)
            print_kpis(cpsat_kpis, label="CP-SAT")

            print("\n[STAGE 7] GREEDY vs CP-SAT COMPARISON")
            comp = compare_plans(greedy_plan, cpsat_plan)
            print_comparison(comp)
        else:
            print("\n  [NOTE] OR-Tools not installed -- skipping CP-SAT stage.")
            print("         Install with:  pip install ortools")
    except Exception as e:
        print(f"\n  [NOTE] CP-SAT stage skipped: {e}")

    # Stage 8: Export
    if export:
        print("\n[STAGE 8] SAVING REPORTS TO outputs/")
        print("-" * 62)
        csv_path = export_csv(greedy_plan, greedy_kpis, "greedy", OUTPUT_DIR)
        txt_path = export_text_report(greedy_plan, greedy_kpis, "greedy", OUTPUT_DIR)
        print(f"  [SAVED] CSV  --> {csv_path}")
        print(f"  [SAVED] TXT  --> {txt_path}")

    print("\n" + "#" * 62)
    print("  SIMULATION COMPLETE")
    print("#" * 62 + "\n")


# ────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Task Scheduler Optimization System -- CLI"
    )
    parser.add_argument("--engine",    choices=["greedy", "cpsat"], default="greedy",
                        help="Scheduling engine (default: greedy)")
    parser.add_argument("--horizon",   type=int, default=72,
                        help="Planning horizon in hours (default: 72)")
    parser.add_argument("--objective", choices=["lateness", "makespan", "hybrid"],
                        default="lateness",
                        help="CP-SAT optimization objective (default: lateness)")
    parser.add_argument("--compare",   action="store_true",
                        help="Run both greedy and CP-SAT and compare results")
    parser.add_argument("--export",    action="store_true",
                        help="Export results to CSV and TXT in outputs/")
    parser.add_argument("--demo",      action="store_true",
                        help="Run full step-by-step simulation walkthrough")
    parser.add_argument("--tasks",     default=TASKS_CSV,
                        help="Path to tasks CSV")
    parser.add_argument("--resources", default=RES_CSV,
                        help="Path to resources CSV")
    args = parser.parse_args()

    print(BANNER)

    # Load data
    print("  [LOAD] Loading data ...")
    try:
        tasks     = load_tasks(args.tasks)
        resources = load_resources(args.resources)
    except FileNotFoundError as e:
        print(f"  [ERROR] {e}")
        sys.exit(1)

    print(f"  [OK] {len(tasks)} tasks loaded from:      {args.tasks}")
    print(f"  [OK] {len(resources)} resources loaded from:  {args.resources}")
    print(f"  [OK] Planning horizon: {args.horizon}h\n")

    # Validate
    print("  [VALIDATE] Checking all tasks ...")
    if not validate_all_tasks(tasks):
        print("  [ERROR] Fix validation errors before running the scheduler.")
        sys.exit(1)
    print("  [OK] All tasks valid\n")

    # Demo mode
    if args.demo:
        run_demo(tasks, resources, args.horizon, args.export)
        return

    # Single engine run
    if not args.compare:
        if args.engine == "greedy":
            print("  Running GREEDY scheduler ...\n")
            plan = greedy_schedule(tasks, resources, horizon=args.horizon)
            print_schedule_table(plan, title="GREEDY SCHEDULE")
            kpis = compute_kpis(plan)
            print_kpis(kpis, label="GREEDY")
            print_ascii_gantt(plan, horizon=args.horizon, scale=2)

        else:  # cpsat
            try:
                from src.cpsat_solver import solve_cpsat, HAS_ORTOOLS
                if not HAS_ORTOOLS:
                    raise ImportError("OR-Tools not found")
            except ImportError:
                print("  [ERROR] OR-Tools not installed. Run:  pip install ortools")
                sys.exit(1)

            print(f"  Running CP-SAT solver (objective={args.objective}) ...\n")
            status, plan = solve_cpsat(
                tasks, resources,
                horizon=args.horizon,
                objective=args.objective
            )
            print(f"  Solver status: {status}\n")
            print_schedule_table(plan, title=f"CP-SAT SCHEDULE ({status})")
            kpis = compute_kpis(plan)
            print_kpis(kpis, label="CP-SAT")
            print_ascii_gantt(plan, horizon=args.horizon, scale=2)

        if args.export:
            csv_path = export_csv(plan, kpis, args.engine, OUTPUT_DIR)
            txt_path = export_text_report(plan, kpis, args.engine, OUTPUT_DIR)
            print(f"\n  [SAVED] CSV --> {csv_path}")
            print(f"  [SAVED] TXT --> {txt_path}\n")

    # Comparison mode
    else:
        print("  Running GREEDY scheduler ...")
        greedy_plan = greedy_schedule(tasks, resources, horizon=args.horizon)
        greedy_kpis = compute_kpis(greedy_plan)

        try:
            from src.cpsat_solver import solve_cpsat, HAS_ORTOOLS
            if not HAS_ORTOOLS:
                raise ImportError
            print("  Running CP-SAT solver ...")
            status, cpsat_plan = solve_cpsat(tasks, resources, horizon=args.horizon)
            cpsat_kpis = compute_kpis(cpsat_plan)
        except ImportError:
            print("  [NOTE] OR-Tools not found -- showing greedy in both columns")
            cpsat_plan = greedy_plan
            cpsat_kpis = greedy_kpis

        print_schedule_table(greedy_plan, title="GREEDY SCHEDULE")
        print_kpis(greedy_kpis, label="GREEDY")
        print_schedule_table(cpsat_plan, title="CP-SAT SCHEDULE")
        print_kpis(cpsat_kpis, label="CP-SAT")
        comp = compare_plans(greedy_plan, cpsat_plan)
        print_comparison(comp)
        print_ascii_gantt(greedy_plan, horizon=args.horizon, scale=2)

        if args.export:
            export_csv(greedy_plan, greedy_kpis, "greedy", OUTPUT_DIR)
            export_csv(cpsat_plan,  cpsat_kpis,  "cpsat",  OUTPUT_DIR)
            export_text_report(greedy_plan, greedy_kpis, "greedy", OUTPUT_DIR)
            export_text_report(cpsat_plan,  cpsat_kpis,  "cpsat",  OUTPUT_DIR)
            print(f"\n  [SAVED] Reports saved to: {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
