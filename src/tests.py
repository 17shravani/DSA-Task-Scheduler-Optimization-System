"""
Unit Tests — Task Scheduler Optimization System
================================================
Tests verify:
  1. Task and Resource loading + validation
  2. Topological sort correctness
  3. Greedy schedule feasibility (skills, shift windows, dependency order)
  4. CP-SAT schedule feasibility (when OR-Tools is installed)
  5. KPI computation accuracy
  6. Comparison utility

Run with:
  python -m pytest src/tests.py -v
"""

import pytest
import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import Task, Resource, load_tasks, load_resources, validate_all_tasks
from src.greedy import topological_sort_by_priority, greedy_schedule
from src.metrics import compute_kpis, compare_plans


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def sample_tasks():
    return [
        Task("T1", "Backend API",   4, 24, 3, "backend",  80, []),
        Task("T2", "Frontend UI",   6, 32, 2, "frontend", 60, ["T1"]),
        Task("T3", "QA Phase 1",    2, 20, 5, "qa",       90, ["T1"]),
        Task("T4", "DB Schema",     8, 40, 1, "backend",  50, []),
        Task("T5", "Auth Module",   3, 36, 4, "backend",  70, ["T4"]),
    ]

@pytest.fixture
def sample_resources():
    return [
        Resource("R1", "Alice",  {"backend", "qa"},   9, 17, 8),
        Resource("R2", "Bob",    {"frontend"},        10, 18, 8),
        Resource("R3", "Carol",  {"backend"},          8, 16, 8),
        Resource("R4", "Dave",   {"qa", "frontend"},   9, 17, 8),
    ]


# ─────────────────────────────────────────────────────────────
# 1. Model Validation Tests
# ─────────────────────────────────────────────────────────────
class TestModels:
    def test_valid_task_has_no_errors(self):
        t = Task("T1", "Test", 4, 24, 3, "backend", 80, [])
        assert t.validate() == []

    def test_invalid_duration(self):
        t = Task("T1", "Test", 0, 24, 3, "backend", 80, [])
        errors = t.validate()
        assert any("duration" in e for e in errors)

    def test_invalid_priority(self):
        t = Task("T1", "Test", 4, 24, 7, "backend", 80, [])  # priority > 5
        errors = t.validate()
        assert any("priority" in e for e in errors)

    def test_negative_profit(self):
        t = Task("T1", "Test", 4, 24, 3, "backend", -10, [])
        errors = t.validate()
        assert any("profit" in e for e in errors)

    def test_resource_skill_check(self, sample_resources):
        r = sample_resources[0]  # Alice: backend + qa
        assert r.can_handle("backend") is True
        assert r.can_handle("frontend") is False

    def test_validate_all_tasks_valid(self, sample_tasks):
        result = validate_all_tasks(sample_tasks)
        assert result is True

    def test_csv_loading(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        tasks     = load_tasks(os.path.join(data_dir, "tasks.csv"))
        resources = load_resources(os.path.join(data_dir, "resources.csv"))
        assert len(tasks)     > 0
        assert len(resources) > 0
        for t in tasks:
            assert t.duration_h > 0
            assert 1 <= t.priority <= 5


# ─────────────────────────────────────────────────────────────
# 2. Topological Sort Tests
# ─────────────────────────────────────────────────────────────
class TestTopologicalSort:
    def test_basic_order(self, sample_tasks):
        order = topological_sort_by_priority(sample_tasks)
        # T1 must come before T2 and T3; T4 must come before T5
        assert order.index("T1") < order.index("T2")
        assert order.index("T1") < order.index("T3")
        assert order.index("T4") < order.index("T5")

    def test_all_tasks_included(self, sample_tasks):
        order = topological_sort_by_priority(sample_tasks)
        assert set(order) == {t.task_id for t in sample_tasks}

    def test_cycle_detection(self):
        cyclic = [
            Task("A", "A", 2, 10, 3, "backend", 50, ["B"]),
            Task("B", "B", 2, 10, 3, "backend", 50, ["A"]),
        ]
        with pytest.raises(ValueError, match="Cycle detected"):
            topological_sort_by_priority(cyclic)

    def test_no_deps_sorted_by_priority(self):
        tasks = [
            Task("T1", "Low",  2, 20, 1, "backend", 10, []),
            Task("T2", "Mid",  2, 20, 3, "backend", 30, []),
            Task("T3", "High", 2, 20, 5, "backend", 50, []),
        ]
        order = topological_sort_by_priority(tasks)
        assert order[0] == "T3"   # highest priority first


# ─────────────────────────────────────────────────────────────
# 3. Greedy Scheduler Feasibility Tests
# ─────────────────────────────────────────────────────────────
class TestGreedyScheduler:
    def test_runs_without_error(self, sample_tasks, sample_resources):
        plan = greedy_schedule(sample_tasks, sample_resources, horizon=72)
        assert isinstance(plan, list)
        assert len(plan) == len(sample_tasks)

    def test_dependency_order_respected(self, sample_tasks, sample_resources):
        plan = greedy_schedule(sample_tasks, sample_resources, horizon=72)
        P    = {p["task_id"]: p for p in plan if not p.get("missed")}

        for t in sample_tasks:
            for dep in t.depends_on:
                if dep in P and t.task_id in P:
                    assert P[t.task_id]["start"] >= P[dep]["end"], (
                        f"{t.task_id} started before dependency {dep} finished"
                    )

    def test_skill_constraint_respected(self, sample_tasks, sample_resources):
        plan = greedy_schedule(sample_tasks, sample_resources, horizon=72)
        task_skill = {t.task_id: t.skill for t in sample_tasks}
        res_skills = {r.res_id: r.skills for r in sample_resources}

        for p in plan:
            if not p.get("missed"):
                assert task_skill[p["task_id"]] in res_skills[p["res_id"]], (
                    f"Task {p['task_id']} assigned to incompatible resource {p['res_id']}"
                )

    def test_no_resource_overlap(self, sample_tasks, sample_resources):
        plan = greedy_schedule(sample_tasks, sample_resources, horizon=72)
        completed = [p for p in plan if not p.get("missed")]

        # Group by resource
        from collections import defaultdict
        by_res = defaultdict(list)
        for p in completed:
            by_res[p["res_id"]].append(p)

        for rid, tasks_on_res in by_res.items():
            sorted_tasks = sorted(tasks_on_res, key=lambda x: x["start"])
            for i in range(1, len(sorted_tasks)):
                prev = sorted_tasks[i - 1]
                curr = sorted_tasks[i]
                assert prev["end"] <= curr["start"], (
                    f"Overlap on {rid}: {prev['task_id']} ends at {prev['end']} "
                    f"but {curr['task_id']} starts at {curr['start']}"
                )

    def test_shift_window_respected(self, sample_tasks, sample_resources):
        plan = greedy_schedule(sample_tasks, sample_resources, horizon=72)
        res_map = {r.res_id: r for r in sample_resources}
        for p in plan:
            if not p.get("missed"):
                r = res_map[p["res_id"]]
                # Determine which day offset this falls on
                day = p["start"] // 24
                day_start = r.shift_start_h + day * 24
                day_end   = r.shift_end_h   + day * 24
                assert p["start"] >= day_start, (
                    f"{p['task_id']} starts before shift on {p['res_id']}"
                )
                assert p["end"]   <= day_end, (
                    f"{p['task_id']} ends after shift on {p['res_id']}"
                )


# ─────────────────────────────────────────────────────────────
# 4. CP-SAT Tests (skipped if OR-Tools not installed)
# ─────────────────────────────────────────────────────────────
try:
    from src.cpsat_solver import solve_cpsat, HAS_ORTOOLS
    SKIP_CPSAT = not HAS_ORTOOLS
except ImportError:
    SKIP_CPSAT = True

@pytest.mark.skipif(SKIP_CPSAT, reason="OR-Tools not installed")
class TestCPSATScheduler:
    def test_feasible_or_optimal(self, sample_tasks, sample_resources):
        status, plan = solve_cpsat(sample_tasks, sample_resources, horizon=72)
        assert status in ("FEASIBLE", "OPTIMAL")

    def test_dependency_order(self, sample_tasks, sample_resources):
        _, plan = solve_cpsat(sample_tasks, sample_resources, horizon=72)
        P = {p["task_id"]: p for p in plan if not p.get("missed")}
        for t in sample_tasks:
            for dep in t.depends_on:
                if dep in P and t.task_id in P:
                    assert P[t.task_id]["start"] >= P[dep]["end"]


# ─────────────────────────────────────────────────────────────
# 5. KPI Tests
# ─────────────────────────────────────────────────────────────
class TestKPIs:
    def test_all_on_time(self):
        plan = [
            {"task_id": "T1", "res_id": "R1", "start": 9, "end": 13,
             "lateness": 0, "on_time": True, "missed": False, "profit": 80, "priority": 3},
            {"task_id": "T2", "res_id": "R2", "start": 10, "end": 16,
             "lateness": 0, "on_time": True, "missed": False, "profit": 60, "priority": 2},
        ]
        kpis = compute_kpis(plan)
        assert kpis["on_time_pct"]      == 100.0
        assert kpis["total_lateness_h"] == 0
        assert kpis["total_profit"]     == 140
        assert kpis["missed_tasks"]     == 0

    def test_with_missed_tasks(self):
        plan = [
            {"task_id": "T1", "res_id": "R1", "start": 9, "end": 13,
             "lateness": 0, "on_time": True, "missed": False, "profit": 80, "priority": 3},
            {"task_id": "T2", "res_id": None, "start": None, "end": None,
             "lateness": None, "on_time": False, "missed": True, "profit": 60, "priority": 2},
        ]
        kpis = compute_kpis(plan)
        assert kpis["missed_tasks"]  == 1
        assert kpis["missed_profit"] == 60
        assert kpis["total_profit"]  == 80

    def test_comparison_utility(self, sample_tasks, sample_resources):
        g_plan = greedy_schedule(sample_tasks, sample_resources, horizon=72)
        # Run greedy again as "cpsat" stand-in for comparison structure test
        c_plan = greedy_schedule(sample_tasks, sample_resources, horizon=72)
        comp   = compare_plans(g_plan, c_plan)
        assert "greedy" in comp
        assert "cpsat"  in comp
        assert "improvement" in comp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
