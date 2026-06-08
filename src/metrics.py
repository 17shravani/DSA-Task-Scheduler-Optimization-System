"""
Metrics & KPI Calculator
=========================
Computes performance indicators for a generated schedule:
  - On-time percentage
  - Total lateness (hours)
  - Total profit achieved
  - Resource utilization per worker
  - Missed task count

DSA Concepts: Aggregation over lists, dictionary accumulation.
"""

from typing import List, Dict, Any


def compute_kpis(plan: List[Dict[str, Any]], tasks_raw=None) -> Dict[str, Any]:
    """
    Compute Key Performance Indicators from a schedule plan.

    Parameters
    ----------
    plan : list of task assignment dicts from greedy or cp-sat solvers

    Returns
    -------
    dict with keys:
      total_tasks       : int
      completed_tasks   : int
      missed_tasks      : int
      on_time_count     : int
      late_count        : int
      on_time_pct       : float  (0-100)
      total_lateness_h  : int    (sum of all lateness hours)
      total_profit      : int    (sum of profit for completed tasks)
      missed_profit     : int    (sum of profit for missed tasks)
      utilization_h     : dict   {res_id: hours_worked}
      makespan          : int    (max end time across all tasks)
    """
    total       = len(plan)
    completed   = [p for p in plan if not p.get("missed", True)]
    missed      = [p for p in plan if p.get("missed", False)]
    on_time     = [p for p in completed if p.get("on_time", False)]
    late_tasks  = [p for p in completed if not p.get("on_time", False)]

    total_lateness = sum(p["lateness"] for p in completed if p["lateness"] is not None)
    total_profit   = sum(p["profit"]   for p in completed)
    missed_profit  = sum(p["profit"]   for p in missed)

    utilization: Dict[str, int] = {}
    for p in completed:
        rid = p["res_id"]
        if rid:
            utilization[rid] = utilization.get(rid, 0) + (p["end"] - p["start"])

    ends    = [p["end"] for p in completed if p["end"] is not None]
    makespan = max(ends) if ends else 0

    on_time_pct = round(100.0 * len(on_time) / total, 1) if total > 0 else 0.0

    return {
        "total_tasks":      total,
        "completed_tasks":  len(completed),
        "missed_tasks":     len(missed),
        "on_time_count":    len(on_time),
        "late_count":       len(late_tasks),
        "on_time_pct":      on_time_pct,
        "total_lateness_h": total_lateness,
        "total_profit":     total_profit,
        "missed_profit":    missed_profit,
        "utilization_h":    utilization,
        "makespan":         makespan,
    }


def compare_plans(
    greedy_plan: List[Dict[str, Any]],
    cpsat_plan:  List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compare greedy vs CP-SAT schedules side-by-side.
    Returns a dict with both KPI sets and improvement deltas.
    """
    gk = compute_kpis(greedy_plan)
    ck = compute_kpis(cpsat_plan)

    return {
        "greedy": gk,
        "cpsat":  ck,
        "improvement": {
            "lateness_reduction_h":  gk["total_lateness_h"] - ck["total_lateness_h"],
            "profit_gain":           ck["total_profit"]     - gk["total_profit"],
            "on_time_pct_gain":      ck["on_time_pct"]      - gk["on_time_pct"],
            "makespan_reduction_h":  gk["makespan"]         - ck["makespan"],
        }
    }
