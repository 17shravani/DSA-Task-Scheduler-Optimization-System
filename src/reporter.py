# -*- coding: utf-8 -*-
"""
Report Generator
=================
Generates human-readable and CSV reports from a schedule plan.

Output formats:
  1. Pretty terminal table
  2. CSV export to outputs/ folder
  3. Text summary report
  4. ASCII Gantt chart
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Any


# ─────────────────────────────────────────────────────────────
# Terminal Table Printer
# ─────────────────────────────────────────────────────────────
def print_schedule_table(plan: List[Dict[str, Any]], title: str = "SCHEDULE") -> None:
    """Print a formatted schedule table to the terminal."""
    print()
    print("=" * 90)
    print(f"  {title}")
    print("=" * 90)

    header = (
        f"  {'Task ID':<8} {'Task Name':<26} {'Resource':<8} "
        f"{'Start':>6} {'End':>5} {'Lateness':>9} {'Status':<12} {'Profit':>7}"
    )
    print(header)
    print("-" * 90)

    completed = [p for p in plan if not p.get("missed", False)]
    missed    = [p for p in plan if p.get("missed", False)]

    for p in sorted(completed, key=lambda x: (x["start"] or 0)):
        status = "[ON-TIME]" if p["on_time"] else "[LATE   ]"
        print(
            f"  {p['task_id']:<8} "
            f"{p['task_name']:<26} "
            f"{p['res_id']:<8} "
            f"{str(p['start'])+'h':>6} "
            f"{str(p['end'])+'h':>5} "
            f"{str(p['lateness'])+'h':>9} "
            f"{status:<12} "
            f"{p['profit']:>7}"
        )

    if missed:
        print()
        print("  MISSED / INFEASIBLE TASKS:")
        print("-" * 90)
        for p in missed:
            print(
                f"  {p['task_id']:<8} "
                f"{p['task_name']:<26} "
                f"{'--':<8} "
                f"{'--':>6} "
                f"{'--':>5} "
                f"{'--':>9} "
                f"[MISSED ]     "
                f"{p['profit']:>7}"
            )

    print("=" * 90)


def print_kpis(kpis: Dict[str, Any], label: str = "") -> None:
    """Print KPI summary block."""
    tag = f" [{label}]" if label else ""
    w = 43
    print()
    print("+" + "-" * w + "+")
    print(f"|  KPI SUMMARY{tag:<{w-13}}|")
    print("+" + "-" * w + "+")
    print(f"|  {'Total Tasks':<22} : {str(kpis['total_tasks']):<{w-27}}|")
    print(f"|  {'Completed':<22} : {str(kpis['completed_tasks']):<{w-27}}|")
    print(f"|  {'Missed':<22} : {str(kpis['missed_tasks']):<{w-27}}|")
    print(f"|  {'On-Time':<22} : {str(kpis['on_time_count']):<{w-27}}|")
    print(f"|  {'Late':<22} : {str(kpis['late_count']):<{w-27}}|")
    print(f"|  {'On-Time %':<22} : {str(kpis['on_time_pct'])+'%':<{w-27}}|")
    print(f"|  {'Total Lateness':<22} : {str(kpis['total_lateness_h'])+'h':<{w-27}}|")
    print(f"|  {'Makespan':<22} : {str(kpis['makespan'])+'h':<{w-27}}|")
    print(f"|  {'Total Profit':<22} : {str(kpis['total_profit']):<{w-27}}|")
    print(f"|  {'Missed Profit':<22} : {str(kpis['missed_profit']):<{w-27}}|")
    print("+" + "-" * w + "+")
    print(f"|  Resource Utilization (hours worked):{' '*(w-39)}|")
    for rid, hrs in sorted(kpis["utilization_h"].items()):
        line = f"    {rid}: {hrs}h"
        print(f"|  {line:<{w-2}}|")
    print("+" + "-" * w + "+")


def print_comparison(comparison: Dict[str, Any]) -> None:
    """Print greedy vs CP-SAT comparison table."""
    gk  = comparison["greedy"]
    ck  = comparison["cpsat"]
    imp = comparison["improvement"]

    print()
    print("=" * 60)
    print("   GREEDY  vs  CP-SAT  COMPARISON")
    print("=" * 60)
    print(f"  {'Metric':<24} {'Greedy':>10} {'CP-SAT':>10} {'Delta':>8}")
    print("-" * 60)

    def row(label, g, c, delta, unit=""):
        sign = "+" if delta > 0 else ""
        print(f"  {label:<24} {str(g)+unit:>10} {str(c)+unit:>10} {sign+str(delta)+unit:>8}")

    row("On-Time %",      gk["on_time_pct"],      ck["on_time_pct"],       imp["on_time_pct_gain"],     "%")
    row("Total Lateness", gk["total_lateness_h"],  ck["total_lateness_h"],  -imp["lateness_reduction_h"],"h")
    row("Total Profit",   gk["total_profit"],       ck["total_profit"],      imp["profit_gain"])
    row("Makespan",       gk["makespan"],            ck["makespan"],          -imp["makespan_reduction_h"],"h")
    row("Missed Tasks",   gk["missed_tasks"],        ck["missed_tasks"],      gk["missed_tasks"]-ck["missed_tasks"])
    print("=" * 60)


def print_ascii_gantt(
    plan: List[Dict[str, Any]],
    horizon: int = 72,
    scale: int = 2
) -> None:
    """
    Print an ASCII Gantt chart grouped by resource.
    Each block character represents `scale` hours.
    """
    completed = [p for p in plan if not p.get("missed", False)]
    if not completed:
        print("  No completed tasks to display.")
        return

    resources = sorted(set(p["res_id"] for p in completed))
    width     = horizon // scale

    print()
    print(f"  GANTT CHART  (each block = {scale} hour(s))")
    print()

    # Header ruler
    ruler_parts = []
    for i in range(width // (10 // scale) + 1):
        h_label = str(i * (10 // scale) * scale)
        ruler_parts.append(h_label.ljust(10 // scale))
    ruler = "".join(ruler_parts)
    print(f"  {'Resource':<12} |{ruler[:width]}")
    print(f"  {'':-<12}-+{'-'*width}")

    for res_id in resources:
        row_chars = ["."] * width
        res_tasks = sorted(
            [p for p in completed if p["res_id"] == res_id],
            key=lambda x: x["start"]
        )
        for p in res_tasks:
            start_col = p["start"] // scale
            end_col   = min(p["end"] // scale, width)
            for col in range(start_col, end_col):
                row_chars[col] = "#"
        bar = "".join(row_chars)
        print(f"  {res_id:<12} |{bar}")

    print()
    print("  Legend: # = task executing  . = idle")
    print()


# ─────────────────────────────────────────────────────────────
# CSV & Text File Exports
# ─────────────────────────────────────────────────────────────
def export_csv(
    plan: List[Dict[str, Any]],
    kpis: Dict[str, Any],
    engine: str = "greedy",
    output_dir: str = "outputs"
) -> str:
    """Export schedule plan to CSV and return the filepath."""
    os.makedirs(output_dir, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(output_dir, f"schedule_{engine}_{ts}.csv")

    fieldnames = [
        "task_id", "task_name", "res_id", "start", "end",
        "lateness", "on_time", "missed", "profit", "priority"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(plan)

    return csv_path


def export_text_report(
    plan: List[Dict[str, Any]],
    kpis: Dict[str, Any],
    engine: str = "greedy",
    output_dir: str = "outputs"
) -> str:
    """Export a full text summary report and return the filepath."""
    os.makedirs(output_dir, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = os.path.join(output_dir, f"report_{engine}_{ts}.txt")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("  TASK SCHEDULER OPTIMIZATION SYSTEM -- PERFORMANCE REPORT\n")
        f.write(f"  Engine   : {engine.upper()}\n")
        f.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")

        f.write("KPI SUMMARY\n")
        f.write("-" * 40 + "\n")
        for k, v in kpis.items():
            f.write(f"  {k:<25}: {v}\n")

        f.write("\nCOMPLETED TASKS\n")
        f.write("-" * 40 + "\n")
        completed = [p for p in plan if not p.get("missed", False)]
        for p in sorted(completed, key=lambda x: (x["start"] or 0)):
            status = "ON-TIME" if p["on_time"] else "LATE"
            f.write(
                f"  {p['task_id']:<6} | {p['task_name']:<28} | "
                f"Res={p['res_id']:<4} | {p['start']}h-{p['end']}h | "
                f"Late={p['lateness']}h | {status}\n"
            )

        missed = [p for p in plan if p.get("missed", False)]
        if missed:
            f.write("\nMISSED TASKS\n")
            f.write("-" * 40 + "\n")
            for p in missed:
                f.write(
                    f"  {p['task_id']:<6} | {p['task_name']:<28} | Profit={p['profit']}\n"
                )

        f.write("\n" + "=" * 70 + "\n")

    return txt_path
