"""
FastAPI Backend Service -- UPGRADED ULTRA PRO MAX VERSION
=========================================================
Exposes REST endpoints to solve scheduling requests with:
  - Custom task and resource lists passed in the payload
  - Complete What-If capabilities (injections, updates)
  - Serving the interactive HTML dashboard at /dashboard
  - SQL run history tracking

Run with:
  uvicorn src.app:app --host 0.0.0.0 --port 8000
"""

import json
import os
import sqlite3
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.models import load_tasks, load_resources, Task, Resource
from src.greedy import greedy_schedule
from src.metrics import compute_kpis

# Try to import CP-SAT solver; fall back gracefully
try:
    from src.cpsat_solver import solve_cpsat, HAS_ORTOOLS
except ImportError:
    HAS_ORTOOLS = False

# ─────────────────────────────────────────────────────────────
# App & DB Setup
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Task Scheduler Optimization API - Ultra Pro Max",
    description="Greedy + CP-SAT scheduler with DAG Visualizations and What-If editing",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "outputs", "sched_runs.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute(
    "CREATE TABLE IF NOT EXISTS runs("
    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "  engine TEXT,"
    "  objective TEXT,"
    "  plan TEXT,"
    "  kpis TEXT,"
    "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    ")"
)
db.commit()


# ─────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────
class TaskDTO(BaseModel):
    task_id: str
    task_name: str
    duration_h: int
    deadline_h: int
    priority: int
    skill: str
    profit: int
    depends_on: List[str] = []


class ResourceDTO(BaseModel):
    res_id: str
    name: str
    skills: List[str]
    shift_start_h: int
    shift_end_h: int
    max_hours_per_day: int = 8


class SolveRequest(BaseModel):
    engine:       str = "greedy"       # "greedy" or "cpsat"
    horizon:      int = 72
    objective:    str = "lateness"     # "lateness" | "makespan" | "hybrid"
    time_limit_s: float = 10.0
    tasks:        Optional[List[TaskDTO]] = None
    resources:    Optional[List[ResourceDTO]] = None


class WhatIfTask(BaseModel):
    task_id:    str
    task_name:  str = "New Task"
    duration_h: int
    deadline_h: int
    priority:   int = 3
    skill:      str
    profit:     int = 50
    depends_on: str = ""            # pipe-separated task IDs


class WhatIfResource(BaseModel):
    res_id:       str
    shift_end_h:  Optional[int] = None
    shift_start_h: Optional[int] = None


class WhatIfRequest(BaseModel):
    engine:          str = "greedy"
    horizon:         int = 72
    add_task:        Optional[WhatIfTask]     = None
    modify_resource: Optional[WhatIfResource] = None
    tasks:           Optional[List[TaskDTO]] = None
    resources:       Optional[List[ResourceDTO]] = None


# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def _load_base():
    tasks     = load_tasks(os.path.join(DATA_DIR, "tasks.csv"))
    resources = load_resources(os.path.join(DATA_DIR, "resources.csv"))
    return tasks, resources


def _run_engine(engine, tasks, resources, horizon, objective, time_limit_s):
    if engine == "greedy":
        plan = greedy_schedule(tasks, resources, horizon=horizon)
        status = "GREEDY"
    elif engine == "cpsat":
        if not HAS_ORTOOLS:
            raise HTTPException(
                status_code=422,
                detail="OR-Tools not installed. Please run pip install ortools."
            )
        status, plan = solve_cpsat(
            tasks, resources,
            horizon=horizon,
            objective=objective,
            time_limit_s=time_limit_s,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown engine '{engine}'")
    return status, plan


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "message": "Task Scheduler Optimization API - Ultra Pro Max is online",
        "endpoints": ["/solve", "/whatif", "/history", "/dashboard", "/docs"],
        "ortools_available": HAS_ORTOOLS,
    }


@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
    try:
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard index.html not found.")


@app.post("/solve")
def solve(req: SolveRequest):
    """Run the scheduler and return an optimized plan + KPIs."""
    if req.tasks is not None and req.resources is not None:
        tasks = [
            Task(
                task_id=t.task_id, task_name=t.task_name,
                duration_h=t.duration_h, deadline_h=t.deadline_h,
                priority=t.priority, skill=t.skill,
                profit=t.profit, depends_on=t.depends_on
            ) for t in req.tasks
        ]
        resources = [
            Resource(
                res_id=r.res_id, name=r.name,
                skills=set(r.skills), shift_start_h=r.shift_start_h,
                shift_end_h=r.shift_end_h, max_hours_per_day=r.max_hours_per_day
            ) for r in req.resources
        ]
    else:
        tasks, resources = _load_base()

    status, plan = _run_engine(
        req.engine, tasks, resources,
        req.horizon, req.objective, req.time_limit_s
    )
    kpis = compute_kpis(plan)

    # Persist to SQLite
    db.execute(
        "INSERT INTO runs(engine, objective, plan, kpis) VALUES (?,?,?,?)",
        (req.engine, req.objective, json.dumps(plan), json.dumps(kpis))
    )
    db.commit()

    return {"status": status, "plan": plan, "kpis": kpis}


@app.post("/whatif")
def whatif(req: WhatIfRequest):
    """
    Tweak constraints and re-solve.
    Supports adding a new task or adjusting a resource shift window.
    """
    if req.tasks is not None and req.resources is not None:
        tasks = [
            Task(
                task_id=t.task_id, task_name=t.task_name,
                duration_h=t.duration_h, deadline_h=t.deadline_h,
                priority=t.priority, skill=t.skill,
                profit=t.profit, depends_on=t.depends_on
            ) for t in req.tasks
        ]
        resources = [
            Resource(
                res_id=r.res_id, name=r.name,
                skills=set(r.skills), shift_start_h=r.shift_start_h,
                shift_end_h=r.shift_end_h, max_hours_per_day=r.max_hours_per_day
            ) for r in req.resources
        ]
    else:
        tasks, resources = _load_base()

    # Inject additional task
    if req.add_task:
        at = req.add_task
        deps = [d.strip() for d in at.depends_on.split("|") if d.strip()]
        new_task = Task(
            task_id=at.task_id, task_name=at.task_name,
            duration_h=at.duration_h, deadline_h=at.deadline_h,
            priority=at.priority, skill=at.skill,
            profit=at.profit, depends_on=deps,
        )
        # Prevent duplication
        tasks = [t for t in tasks if t.task_id != at.task_id]
        tasks.append(new_task)

    # Modify resource shift
    if req.modify_resource:
        mr = req.modify_resource
        for r in resources:
            if r.res_id == mr.res_id:
                if mr.shift_end_h   is not None: r.shift_end_h   = mr.shift_end_h
                if mr.shift_start_h is not None: r.shift_start_h = mr.shift_start_h

    status, plan = _run_engine(
        req.engine, tasks, resources, req.horizon, "lateness", 10.0
    )
    kpis = compute_kpis(plan)
    return {"status": status, "plan": plan, "kpis": kpis}


@app.get("/history")
def history(limit: int = 20):
    """Return the last N solver runs from the database."""
    rows = db.execute(
        "SELECT id, engine, objective, kpis, created_at "
        "FROM runs ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    result = []
    for row in rows:
        result.append({
            "id":         row[0],
            "engine":     row[1],
            "objective":  row[2],
            "kpis":       json.loads(row[3]),
            "created_at": row[4],
        })
    return {"runs": result}
