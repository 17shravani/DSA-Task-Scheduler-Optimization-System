# 📅 Task Scheduler Optimization System

> **DSA Course Project** · Greedy + CP-SAT · FastAPI + Interactive Dashboard

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![OR-Tools](https://img.shields.io/badge/OR--Tools-CP--SAT-green?logo=google)](https://developers.google.com/optimization)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-teal?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📌 Project Overview

The **Task Scheduler Optimization System** is an industry-grade DSA project that models real-world scheduling as a combinatorial optimization problem. It assigns tasks to time slots and human resources while minimizing lateness and cost, respecting task dependencies, skill requirements, and working-hour constraints.

This project demonstrates mastery of core DSA and system design concepts useful for **Software Developer**, **Backend Engineer**, **System Design**, and **DSA Interview** roles.

---

## 🧩 Problem Statement

Given a set of **tasks** (with durations, deadlines, priorities, required skills, and dependencies) and a set of **resources** (with skills and shift windows), find an assignment of tasks to resources and time slots that:

- ✅ Respects all task-dependency ordering (precedence constraints)
- ✅ Assigns each task only to a resource with the matching skill
- ✅ Ensures no resource works two tasks simultaneously (no-overlap)
- ✅ Keeps all tasks within the resource's working-hour window
- 🎯 **Minimizes** total lateness, makespan, or a hybrid objective

This mirrors real-world problems in:
- 🖥️ **CPU & OS Scheduling** — process priority and deadline scheduling
- 🏭 **Manufacturing** — job-shop scheduling with machine constraints
- 🏢 **Project Management** — sprint planning with team skill requirements
- ☁️ **Cloud Computing** — job queues with resource capacity constraints
- 🚚 **Logistics** — delivery routing with time windows

---

## 🧠 DSA Concepts Used

| Concept | Where Used | Complexity |
|---|---|---|
| **Min-Heap / Priority Queue** | Task selection in topological BFS | O(log n) |
| **DAG + Kahn's BFS Topological Sort** | Dependency ordering | O(V + E) |
| **Greedy Algorithm** | Fast heuristic scheduler | O(n · r) |
| **Sorting** | Priority + deadline tie-breaking | O(n log n) |
| **Hash Map (Dictionary)** | Task lookup, resource state tracking | O(1) avg |
| **Constraint Programming (CP-SAT)** | Optimal solver via OR-Tools | Branch & Bound |
| **Interval Variables** | No-overlap scheduling constraints | — |
| **Directed Acyclic Graph (DAG)** | Dependency representation | O(V + E) |
| **Dynamic Programming** | Lateness penalty accumulation | O(n) |
| **Queue (deque)** | BFS frontier in topological sort | O(1) |

---

## ⚙️ Algorithm Explanation

### Workflow

```
Task Input CSV
     │
     ▼
┌─────────────┐
│  Validation │  ← Check duration > 0, priority 1-5, skill not empty
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│  Topological Sort (BFS)  │  ← Kahn's algorithm + min-heap
│  Priority Queue ordering │     tie-break: -priority, +deadline
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  Engine Choice                       │
│  ┌──────────────┐  ┌──────────────┐ │
│  │    GREEDY    │  │   CP-SAT     │ │
│  │  O(n log n)  │  │  Optimal     │ │
│  └──────────────┘  └──────────────┘ │
└──────────────────────────────────────┘
           │
           ▼
┌────────────────────────┐
│  Schedule Plan         │  ← {task_id, res_id, start, end}
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│  KPI Computation       │  ← on_time%, lateness, profit, utilization
└──────────┬─────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Output                      │
│  • Terminal table + Gantt    │
│  • CSV + TXT report          │
│  • FastAPI JSON response     │
│  • Interactive HTML Dashboard│
└──────────────────────────────┘
```

### Greedy Algorithm Steps

1. Build dependency graph (DAG)
2. Initialize min-heap with all tasks of indegree=0
3. Pop highest-priority ready task from heap
4. For each compatible resource, compute earliest feasible start
5. Score candidates: `score = lateness × (6 - priority)`
6. Assign to lowest-score resource, advance resource cursor
7. Unlock children tasks (reduce indegree), push to heap if ready
8. Repeat until all tasks scheduled

### CP-SAT Formulation

```
Variables:
  start[t] ∈ [0, H]     integer start hour
  end[t]   ∈ [0, H]     integer end hour
  x[t,r]   ∈ {0,1}      1 if task t assigned to resource r

Constraints:
  Σ_r x[t,r] = 1                          ← each task assigned once
  AddNoOverlap(optional_itvs[r])           ← no resource double-booked
  start[t] ≥ end[dep]  ∀ dep ∈ deps[t]   ← precedence
  start[t] ≥ shift_start + 24k            ← shift window (day k)
  end[t]   ≤ shift_end   + 24k

Objective:
  Minimize Σ_t w[t] × max(0, end[t] - deadline[t])
  where w[t] = 6 - priority[t]  (low priority penalized more)
```

---

## 🗂️ Folder Structure

```
DSA-Task Scheduler Optimization System/
│
├── data/
│   ├── tasks.csv           ← Task dataset (10 sample tasks)
│   └── resources.csv       ← Resource dataset (4 workers)
│
├── src/
│   ├── __init__.py
│   ├── models.py           ← Task, Resource dataclasses + CSV loaders
│   ├── greedy.py           ← Greedy heuristic scheduler (topological sort + heap)
│   ├── cpsat_solver.py     ← CP-SAT optimal solver (OR-Tools)
│   ├── metrics.py          ← KPI computation + comparison
│   ├── reporter.py         ← Terminal tables, ASCII Gantt, CSV/TXT export
│   ├── app.py              ← FastAPI backend (/solve, /whatif, /history)
│   └── tests.py            ← Full unit test suite (pytest)
│
├── dashboard/
│   └── index.html          ← Interactive Gantt + KPI dashboard (standalone HTML)
│
├── outputs/                ← Generated CSV/TXT reports (git-ignored)
│   └── .gitkeep
│
├── images/                 ← Screenshots for README
├── docs/                   ← Documentation
│
├── main.py                 ← CLI entry point
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10 or higher
- pip

### Step 1 — Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/Task-Scheduler-Optimization-System.git
cd Task-Scheduler-Optimization-System
```

### Step 2 — Create virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

> **Note:** `ortools` is optional but recommended for the CP-SAT solver.
> The greedy heuristic works without it.

---

## ▶️ How to Run

### 1. CLI — Greedy Scheduler (default)
```bash
python main.py
```

### 2. CLI — Full Simulation Walkthrough
```bash
python main.py --demo --export
```

### 3. CLI — CP-SAT Optimal Solver
```bash
python main.py --engine cpsat --objective lateness
```

### 4. CLI — Compare Both Engines
```bash
python main.py --compare --export
```

### 5. Run FastAPI Backend
```bash
uvicorn src.app:app --reload --port 8000
# API docs available at: http://localhost:8000/docs
```

### 6. Open Interactive Dashboard
Open `dashboard/index.html` in your browser.
- In **standalone mode** → click "Load Demo Schedule"  
- With backend running → click "Solve" to get live results

### 7. Run Unit Tests
```bash
python -m pytest src/tests.py -v
```

---

## 📊 Sample Output

```
╔══════════════════════════════════════════════════════════════╗
║        Task Scheduler Optimization System  v1.0             ║
╚══════════════════════════════════════════════════════════════╝

════════════════════════════════════════════════════════════════
  📋  GREEDY SCHEDULE
════════════════════════════════════════════════════════════════
Task ID  Task Name                    Resource   Start   End  Lateness   Status    Profit
-------- ---------------------------- ---------- ----- ----- --------- ---------- ------
T3       QA Testing Phase 1           R1           9h   11h        0h  ✅ ON-TIME     90
T1       Backend API Setup            R3           8h   12h        0h  ✅ ON-TIME     80
T4       Database Schema              R1          11h   19h        2h  ⚠️  LATE        50
T5       Authentication Module        R3          12h   15h        0h  ✅ ON-TIME     70
T2       Frontend UI Design           R2          12h   18h        0h  ✅ ON-TIME     60
...
════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────┐
│  📊  KPI SUMMARY [GREEDY]               │
├─────────────────────────────────────────┤
│  Total Tasks        : 10               │
│  Completed          : 10               │
│  On-Time            : 9                │
│  On-Time %          : 90.0%            │
│  Total Lateness     : 2h               │
│  Total Profit       : 715              │
└─────────────────────────────────────────┘
```

---

## 🔮 Features

- [x] **Greedy Heuristic Scheduler** — fast, priority-aware, dependency-safe
- [x] **CP-SAT Optimal Solver** — provably optimal with OR-Tools
- [x] **What-If Analysis** — add tasks or modify resource shifts and re-solve
- [x] **FastAPI REST Backend** — `/solve`, `/whatif`, `/history` endpoints
- [x] **Interactive Dashboard** — Gantt chart, KPI cards, utilization bars
- [x] **ASCII Gantt Chart** — terminal visualization of execution timeline
- [x] **CSV & Text Reports** — auto-saved to `outputs/`
- [x] **SQLite Persistence** — stores all solver runs for history
- [x] **Full Unit Tests** — pytest suite covering all components
- [x] **Cycle Detection** — raises error if dependency graph has cycles
- [x] **Shift Window Enforcement** — tasks constrained to working hours

---

## 📅 Day-Wise Proof Building Plan

| Day | Task | Commit Message |
|-----|------|----------------|
| Day 1 | Setup + data CSV + models.py | `feat: project setup, Task and Resource models` |
| Day 2 | Topological sort + sorting logic | `feat: Kahn's BFS topo sort with priority heap` |
| Day 3 | Greedy scheduler + ASCII Gantt | `feat: greedy heuristic scheduler with Gantt output` |
| Day 4 | CP-SAT solver + comparison | `feat: CP-SAT solver with OR-Tools, comparison report` |
| Day 5 | FastAPI backend + KPIs | `feat: FastAPI /solve /whatif endpoints, KPI metrics` |
| Day 6 | Dashboard + README + tests | `docs: interactive dashboard, unit tests, README` |

---

## 🎤 Interview Preparation — 10 Q&A

### Q1: Explain your project.
**HR Answer:** "I built a Task Scheduler Optimization System that automatically organizes and assigns tasks to team members in the most efficient order. It considers deadlines, priority, skills, and working hours to create an optimal schedule, similar to how real-world tools like JIRA or cloud job schedulers work."

**Technical Answer:** "The system models scheduling as a combinatorial optimization problem on a Directed Acyclic Graph. Task dependencies are processed using Kahn's BFS topological sort with a min-heap for priority ordering. I implemented two engines: a greedy heuristic (O(n log n)) for speed, and a CP-SAT solver using Google OR-Tools for global optimality. The objective minimizes weighted lateness subject to no-overlap, skill-matching, and shift-window constraints."

---

### Q2: What problem does this project solve?
**Answer:** It solves the constraint-aware task scheduling problem: given multiple tasks with different durations, deadlines, priorities, and skill requirements, and multiple workers with different skills and working hours, find an assignment that maximizes on-time completion and profit while respecting all constraints. This is NP-hard in general, which is why we use both a fast heuristic and an exact solver.

---

### Q3: Which DSA concepts did you use?
**Answer:** Min-Heap and Priority Queue (O(log n) task selection), DAG with Kahn's BFS topological sort (O(V+E)), Greedy algorithm for heuristic scheduling, Sorting (O(n log n)) for tie-breaking, Hash Maps for O(1) task and resource lookup, Interval variables and constraint propagation for CP-SAT, and Cycle detection on the dependency graph.

---

### Q4: Why did you use a priority queue instead of simple sorting?
**Answer:** Simple sorting is static — it produces a fixed order upfront. A priority queue (min-heap) is dynamic — as tasks complete and unlock their dependencies, newly-eligible tasks are immediately inserted into the heap and ordered correctly. This gives us O(log n) insertion and O(log n) extraction while maintaining the invariant that we always process the highest-priority ready task next.

---

### Q5: How does the greedy algorithm work?
**Answer:** It uses a topological BFS order to process tasks. For each task in this order, it iterates over all compatible resources and computes the earliest feasible slot respecting shift windows and the resource's current time cursor. Each candidate is scored as `lateness × (6 - priority)` — lower is better. The task is assigned to the best-scoring candidate. This is a locally optimal choice at each step.

---

### Q6: Why is CP-SAT better than greedy?
**Answer:** Greedy is fast (O(n log n)) but makes irrevocable local decisions that can lead to suboptimal global solutions. CP-SAT models the full solution space with interval variables, precedence constraints, and resource no-overlap constraints, then searches using branch-and-bound with constraint propagation. It can prove optimality or find a provably near-optimal solution within a time budget. The trade-off is computational cost: CP-SAT is exponential in worst case but uses sophisticated pruning.

---

### Q7: What is a topological sort and why do you need it?
**Answer:** A topological sort of a DAG produces a linear ordering of nodes such that for every directed edge (u → v), u appears before v. We need it because task B that depends on task A cannot start until A is complete. Kahn's algorithm computes this in O(V+E) using BFS: maintain in-degrees, start with zero-in-degree nodes, process each node and reduce in-degrees of its neighbors.

---

### Q8: How do you detect dependency cycles?
**Answer:** In Kahn's algorithm, if the topological sort produces fewer nodes than the total number of tasks, it means some tasks were never added to the queue — their in-degrees never reached zero because they are part of a cycle. I raise a `ValueError` with the list of tasks involved in the cycle.

---

### Q9: Where is this type of system used in real life?
**Answer:** CPU scheduling (priority + deadline), manufacturing job-shop scheduling (machine constraints), cloud computing job queues (resource capacity), project management tools like JIRA/Asana (sprint planning), hospital staff scheduling (skill-matching + shift windows), logistics and delivery routing (time windows), and exam timetabling (room + invigilator constraints).

---

### Q10: How can this project be improved further?
**Answer:** Several extensions are possible: multi-skill tasks requiring a team formation, sequence-dependent setup times between certain task pairs (changeover costs), travel time between field service locations, rolling-horizon re-optimization as new tasks arrive, calendar-aware scheduling with holidays and PTO, and machine learning to predict task durations from historical data.

---

## 📜 License
MIT License — free for educational and commercial use.

---

## 👩‍💻 Author
Built as a DSA course project demonstrating real-world scheduling algorithms.
