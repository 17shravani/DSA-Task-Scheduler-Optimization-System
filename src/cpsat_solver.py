"""
CP-SAT Optimal Solver
======================
Uses Google OR-Tools CP-SAT (Constraint Programming - Satisfiability) to find
a globally optimal or near-optimal schedule.

DSA / CS Concepts Demonstrated:
  - Constraint Programming (CP)
  - Integer Linear Programming (ILP) modeling
  - Interval Variables & No-Overlap constraints
  - Precedence / dependency graph constraints
  - Multi-objective optimization (lateness, makespan, hybrid)
  - Binary decision variables for resource assignment

Why CP-SAT?
  The greedy heuristic is fast (O(n log n)) but cannot guarantee optimality.
  CP-SAT searches the full solution space using propagation + branch-and-bound,
  guaranteeing an optimal solution within a time budget.
"""

from typing import List, Dict, Any, Tuple, Optional

try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False

from src.models import Task, Resource


# ─────────────────────────────────────────────────────────────
# Solver Status Labels
# ─────────────────────────────────────────────────────────────
STATUS_LABELS = {
    0: "UNKNOWN",
    1: "MODEL_INVALID",
    2: "FEASIBLE",
    3: "INFEASIBLE",
    4: "OPTIMAL",
}


def solve_cpsat(
    tasks: List[Task],
    resources: List[Resource],
    horizon: int = 72,
    objective: str = "lateness",   # "lateness" | "makespan" | "hybrid"
    time_limit_s: float = 15.0,
    num_workers: int = 4,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Solve the scheduling problem with CP-SAT.

    Parameters
    ----------
    tasks       : list of Task objects
    resources   : list of Resource objects
    horizon     : planning horizon in hours (all tasks must end ≤ horizon)
    objective   : what to minimize — "lateness", "makespan", or "hybrid"
    time_limit_s: solver wall-clock budget in seconds
    num_workers : parallel search threads

    Returns
    -------
    (status_str, plan)
      status_str : "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN"
      plan       : list of dicts {task_id, task_name, res_id, start, end,
                                  lateness, on_time, missed, profit, priority}
    """
    if not HAS_ORTOOLS:
        raise ImportError(
            "OR-Tools is not installed.\n"
            "Install it with:  pip install ortools\n"
            "Falling back to greedy solver is recommended."
        )

    m   = cp_model.CpModel()
    H   = horizon
    T   = {t.task_id: t for t in tasks}
    R   = {r.res_id:  r for r in resources}

    # ── Decision Variables ─────────────────────────────────
    # start[tid], end[tid]  : integer hour within [0, H]
    # itv[tid]              : interval variable (links start, dur, end)
    start = {tid: m.NewIntVar(0, H, f"s_{tid}") for tid in T}
    end   = {tid: m.NewIntVar(0, H, f"e_{tid}") for tid in T}
    dur   = {tid: T[tid].duration_h             for tid in T}
    itv   = {
        tid: m.NewIntervalVar(start[tid], dur[tid], end[tid], f"itv_{tid}")
        for tid in T
    }

    # x[(tid, rid)] = 1  iff task tid is assigned to resource rid
    x = {
        (tid, rid): m.NewBoolVar(f"x_{tid}_{rid}")
        for tid in T
        for rid in R
        if T[tid].skill in R[rid].skills
    }

    # ── Constraints ────────────────────────────────────────

    # 1. Each task is assigned to exactly one compatible resource
    for tid in T:
        compatible = [x[(tid, rid)] for rid in R if (tid, rid) in x]
        if not compatible:
            raise ValueError(
                f"Task '{tid}' (skill='{T[tid].skill}') has NO compatible resource!"
            )
        m.Add(sum(compatible) == 1)

    # 2. No two tasks on the same resource may overlap
    #    Use optional interval variables: active only when x[(tid,rid)] == 1
    for rid in R:
        opt_itvs = []
        for tid in T:
            if (tid, rid) in x:
                opt_itv = m.NewOptionalIntervalVar(
                    start[tid], dur[tid], end[tid],
                    x[(tid, rid)],
                    f"oi_{tid}_{rid}"
                )
                opt_itvs.append(opt_itv)
        if opt_itvs:
            m.AddNoOverlap(opt_itvs)

    # 3. Precedence constraints: task cannot start before all dependencies finish
    for tid in T:
        for dep in T[tid].depends_on:
            if dep in T:
                m.Add(start[tid] >= end[dep])

    # 4. Shift-window constraints:
    #    If task tid is on resource rid, it must start/end within a valid shift.
    #    We allow multi-day: day offset k ∈ {0,1,2,...}
    #    start[tid] >= shift_start + 24*k
    #    end[tid]   <= shift_end   + 24*k
    for (tid, rid), var in x.items():
        s_h = R[rid].shift_start_h
        e_h = R[rid].shift_end_h
        max_days = H // 24 + 2
        k = m.NewIntVar(0, max_days, f"k_{tid}_{rid}")
        m.Add(start[tid] >= s_h + 24 * k).OnlyEnforceIf(var)
        m.Add(end[tid]   <= e_h + 24 * k).OnlyEnforceIf(var)

    # ── Objective ──────────────────────────────────────────
    # Lateness: max(0, end - deadline)  (soft constraint — penalized, not forbidden)
    laten = {}
    for tid in T:
        laten[tid] = m.NewIntVar(0, H, f"late_{tid}")
        m.Add(laten[tid] >= end[tid] - T[tid].deadline_h)
        m.Add(laten[tid] >= 0)

    if objective == "lateness":
        # Weight lateness by inverse priority (low-priority tasks penalized more
        # for being late, encouraging high-priority tasks to be on time)
        weights = {tid: max(1, 6 - T[tid].priority) for tid in T}
        m.Minimize(sum(weights[tid] * laten[tid] for tid in T))

    elif objective == "makespan":
        Cmax = m.NewIntVar(0, H, "Cmax")
        m.AddMaxEquality(Cmax, [end[tid] for tid in T])
        m.Minimize(Cmax)

    else:  # hybrid
        Cmax = m.NewIntVar(0, H, "Cmax")
        m.AddMaxEquality(Cmax, [end[tid] for tid in T])
        m.Minimize(sum(laten.values()) + Cmax)

    # ── Solve ──────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers  = num_workers
    solver.parameters.log_search_progress = False

    status_code = solver.Solve(m)
    status_str  = STATUS_LABELS.get(status_code, "UNKNOWN")

    # ── Extract Solution ───────────────────────────────────
    plan: List[Dict[str, Any]] = []

    if status_code in (2, 4):   # FEASIBLE or OPTIMAL
        for tid in T:
            t      = T[tid]
            st     = solver.Value(start[tid])
            et     = solver.Value(end[tid])
            late   = max(0, et - t.deadline_h)
            rid    = next(
                (r for (tt, r), var in x.items()
                 if tt == tid and solver.Value(var) == 1),
                None
            )
            plan.append({
                "task_id":   tid,
                "task_name": t.task_name,
                "res_id":    rid,
                "start":     st,
                "end":       et,
                "lateness":  late,
                "on_time":   late == 0,
                "missed":    False,
                "profit":    t.profit,
                "priority":  t.priority,
            })
    else:
        # Return empty plan with all tasks marked infeasible
        for tid in T:
            t = T[tid]
            plan.append({
                "task_id":   tid,
                "task_name": t.task_name,
                "res_id":    None,
                "start":     None,
                "end":       None,
                "lateness":  None,
                "on_time":   False,
                "missed":    True,
                "profit":    t.profit,
                "priority":  t.priority,
            })

    return status_str, plan
