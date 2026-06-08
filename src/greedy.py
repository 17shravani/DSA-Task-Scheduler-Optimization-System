"""
Greedy Heuristic Scheduler
============================
Implements a topology-aware greedy scheduler using:
  - Kahn's algorithm (BFS topological sort) for dependency ordering
  - Min-Heap / Priority Queue for task selection (highest priority, earliest deadline)
  - Earliest-feasible-slot assignment per resource

DSA Concepts:
  - Graph (DAG) + BFS topological sort        O(V+E)
  - Binary Heap / Priority Queue              O(log n) per push/pop
  - Greedy algorithm                          O(n * r) assignment
  - Sorting                                   O(n log n)
"""

import heapq
from collections import defaultdict, deque
from typing import List, Dict, Any

from src.models import Task, Resource


# ─────────────────────────────────────────────────────────────
# Topological Sort (Kahn's BFS algorithm)
# ─────────────────────────────────────────────────────────────
def topological_sort_by_priority(tasks: List[Task]) -> List[str]:
    """
    Returns task IDs in a topological order that respects dependencies.
    Among tasks with equal topological depth, breaks ties by:
      1. Higher priority first (descending)
      2. Earlier deadline first (ascending)

    Uses Kahn's BFS algorithm — a classic graph algorithm for DAG ordering.
    Time Complexity: O(V + E)  where V = tasks, E = dependency edges
    """
    # Build adjacency structures
    indegree: Dict[str, int] = defaultdict(int)
    children: Dict[str, List[str]] = defaultdict(list)
    lookup: Dict[str, Task] = {t.task_id: t for t in tasks}

    for t in tasks:
        if t.task_id not in indegree:
            indegree[t.task_id] = 0
        for dep in t.depends_on:
            indegree[t.task_id] += 1
            children[dep].append(t.task_id)

    # Initialize queue with tasks that have no dependencies
    # Using a min-heap: (-priority, deadline, task_id) for stable ordering
    heap = []
    for t in tasks:
        if indegree[t.task_id] == 0:
            heapq.heappush(heap, (-t.priority, t.deadline_h, t.task_id))

    topo_order: List[str] = []

    while heap:
        neg_prio, ddl, tid = heapq.heappop(heap)
        topo_order.append(tid)

        # Reduce indegree of children; push newly ready tasks
        for child_id in children[tid]:
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                child = lookup[child_id]
                heapq.heappush(heap, (-child.priority, child.deadline_h, child_id))

    # Cycle detection
    if len(topo_order) != len(tasks):
        raise ValueError(
            "Cycle detected in task dependencies! "
            "Tasks with cycles: " + str(set(t.task_id for t in tasks) - set(topo_order))
        )

    return topo_order


# ─────────────────────────────────────────────────────────────
# Greedy Scheduler
# ─────────────────────────────────────────────────────────────
def greedy_schedule(
    tasks: List[Task],
    resources: List[Resource],
    horizon: int = 72
) -> List[Dict[str, Any]]:
    """
    Greedy scheduler that assigns tasks to resources.

    Algorithm:
      1. Topological sort with priority/deadline tie-breaking (uses a min-heap)
      2. For each task in topo order:
         a. Find earliest feasible start time on each compatible resource
         b. Score each candidate: minimize lateness, maximize priority
         c. Assign task to best-scored (resource, start_time) pair

    Returns:
        plan: list of dicts  {task_id, res_id, start, end, lateness, on_time}

    Time Complexity: O(n log n + n * r)
      where n = number of tasks, r = number of resources
    """
    topo_order = topological_sort_by_priority(tasks)
    lookup: Dict[str, Task] = {t.task_id: t for t in tasks}

    # Track the next available time for each resource (per day)
    res_next: Dict[str, int] = {r.res_id: r.shift_start_h for r in resources}
    res_day:  Dict[str, int] = {r.res_id: 0 for r in resources}
    res_map:  Dict[str, Resource] = {r.res_id: r for r in resources}

    # Track when each task finishes (for dependency enforcement)
    finish_time: Dict[str, int] = {}

    plan: List[Dict[str, Any]] = []

    def earliest_start(res: Resource, dep_end: int) -> int:
        """
        Find the earliest slot start for a resource, respecting:
          - current resource cursor
          - dependency finish time
          - shift window (rolls to next day if needed)
        """
        day = res_day[res.res_id]
        cur = max(res_next[res.res_id], dep_end, res.shift_start_h + day * 24)

        # Roll forward to next valid shift day if outside window
        while True:
            day_start = res.shift_start_h + day * 24
            day_end   = res.shift_end_h   + day * 24

            if cur < day_start:
                cur = day_start

            t = lookup[topo_order[0]] if topo_order else None
            # We'll check duration fit below in the caller
            if cur >= day_start and cur <= day_end:
                return cur
            # Advance to next day
            day += 1
            cur = res.shift_start_h + day * 24
            if cur > horizon:
                return None  # no feasible slot

    for tid in topo_order:
        t = lookup[tid]

        # Earliest start = max of all dependency finish times
        dep_end = max((finish_time[d] for d in t.depends_on), default=0)

        best_score  = None
        best_start  = None
        best_res_id = None

        for res in resources:
            if not res.can_handle(t.skill):
                continue  # skill mismatch — skip

            day = res_day[res.res_id]
            cur = max(res_next[res.res_id], dep_end, res.shift_start_h + day * 24)

            # Roll to a valid shift window that fits the task duration
            attempts = 0
            while attempts < 10:
                day_start = res.shift_start_h + day * 24
                day_end   = res.shift_end_h   + day * 24

                if cur < day_start:
                    cur = day_start

                if cur + t.duration_h <= day_end and cur <= horizon:
                    break  # found a fit in this day
                elif cur + t.duration_h > day_end:
                    day += 1
                    cur = max(res_next[res.res_id], dep_end, res.shift_start_h + day * 24)
                else:
                    cur = None
                    break
                attempts += 1
            else:
                cur = None

            if cur is None or cur + t.duration_h > horizon:
                continue  # no feasible slot within horizon

            end_time = cur + t.duration_h
            lateness = max(0, end_time - t.deadline_h)

            # Score: minimize lateness (weighted by inverse priority), then prefer earlier
            score = (lateness * (6 - t.priority), cur, res.res_id)

            if best_score is None or score < best_score:
                best_score  = score
                best_start  = cur
                best_res_id = res.res_id

        if best_start is None:
            # Skip this task (infeasible within horizon) — mark as missed
            plan.append({
                "task_id":  tid,
                "task_name": t.task_name,
                "res_id":   None,
                "start":    None,
                "end":      None,
                "lateness": None,
                "on_time":  False,
                "missed":   True,
                "profit":   t.profit,
                "priority": t.priority,
            })
            finish_time[tid] = dep_end  # treat as if it finished at dep_end for downstream
            continue

        end_time = best_start + t.duration_h
        lateness = max(0, end_time - t.deadline_h)

        plan.append({
            "task_id":   tid,
            "task_name": t.task_name,
            "res_id":    best_res_id,
            "start":     best_start,
            "end":       end_time,
            "lateness":  lateness,
            "on_time":   lateness == 0,
            "missed":    False,
            "profit":    t.profit,
            "priority":  t.priority,
        })

        finish_time[tid] = end_time
        res_next[best_res_id] = end_time
        # Update day cursor
        res_day[best_res_id] = (end_time - res_map[best_res_id].shift_start_h) // 24

    return plan
