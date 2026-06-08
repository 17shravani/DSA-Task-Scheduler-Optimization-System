"""
Task Scheduler Optimization System
====================================
Task class definition and data loading utilities.

DSA Concepts Used:
- Object-Oriented Programming (encapsulation)
- Data validation
- CSV parsing
"""

import csv
import os
from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────────────────────────────────────
# Task Data Class
# ─────────────────────────────────────────────────────────────
@dataclass
class Task:
    """
    Represents a single schedulable task.

    Attributes:
        task_id     : unique identifier (e.g. "T1")
        task_name   : human-readable name
        duration_h  : execution time in hours (must be > 0)
        deadline_h  : absolute deadline in hours from t=0
        priority    : integer 1-5 (5 = highest importance)
        skill       : skill category required ("backend", "frontend", "qa")
        profit      : importance / profit score for this task
        depends_on  : list of task_ids that must finish before this starts
    """
    task_id:    str
    task_name:  str
    duration_h: int
    deadline_h: int
    priority:   int
    skill:      str
    profit:     int
    depends_on: List[str] = field(default_factory=list)

    # convenience aliases used by solver modules
    @property
    def dur(self): return self.duration_h
    @property
    def ddl(self): return self.deadline_h
    @property
    def prio(self): return self.priority
    @property
    def deps(self): return self.depends_on

    def validate(self) -> List[str]:
        """
        Validate task fields.
        Returns a list of error messages; empty list means valid.
        """
        errors = []
        if not self.task_id:
            errors.append("task_id cannot be empty")
        if self.duration_h <= 0:
            errors.append(f"[{self.task_id}] duration_h must be > 0 (got {self.duration_h})")
        if self.deadline_h <= 0:
            errors.append(f"[{self.task_id}] deadline_h must be > 0 (got {self.deadline_h})")
        if not (1 <= self.priority <= 5):
            errors.append(f"[{self.task_id}] priority must be 1-5 (got {self.priority})")
        if self.profit < 0:
            errors.append(f"[{self.task_id}] profit cannot be negative (got {self.profit})")
        if not self.skill:
            errors.append(f"[{self.task_id}] skill cannot be empty")
        return errors

    def __repr__(self):
        return (
            f"Task({self.task_id!r}, name={self.task_name!r}, "
            f"dur={self.duration_h}h, ddl={self.deadline_h}h, "
            f"prio={self.priority}, skill={self.skill!r}, profit={self.profit})"
        )


# ─────────────────────────────────────────────────────────────
# Resource Data Class
# ─────────────────────────────────────────────────────────────
@dataclass
class Resource:
    """
    Represents a worker / machine that can execute tasks.

    Attributes:
        res_id          : unique identifier (e.g. "R1")
        name            : human-readable name
        skills          : set of skill categories this resource can handle
        shift_start_h   : start of working window (hours from t=0, e.g. 9)
        shift_end_h     : end of working window   (hours from t=0, e.g. 17)
        max_hours_per_day: daily capacity cap
    """
    res_id:           str
    name:             str
    skills:           set
    shift_start_h:    int
    shift_end_h:      int
    max_hours_per_day:int

    def can_handle(self, skill: str) -> bool:
        return skill in self.skills

    def __repr__(self):
        return (
            f"Resource({self.res_id!r}, name={self.name!r}, "
            f"skills={self.skills}, shift={self.shift_start_h}-{self.shift_end_h}h)"
        )


# ─────────────────────────────────────────────────────────────
# CSV Loaders
# ─────────────────────────────────────────────────────────────
def load_tasks(path: str = None) -> List[Task]:
    """
    Load tasks from a CSV file.
    Expected columns:
      task_id, task_name, duration_h, deadline_h, priority, skill, profit, depends_on
    """
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "tasks.csv")
    path = os.path.abspath(path)

    tasks = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dep_str = row.get("depends_on", "").strip()
            deps = [d.strip() for d in dep_str.split("|") if d.strip()] if dep_str else []
            t = Task(
                task_id=row["task_id"].strip(),
                task_name=row.get("task_name", row["task_id"]).strip(),
                duration_h=int(row["duration_h"]),
                deadline_h=int(row["deadline_h"]),
                priority=int(row["priority"]),
                skill=row["skill"].strip(),
                profit=int(row.get("profit", 0)),
                depends_on=deps,
            )
            tasks.append(t)
    return tasks


def load_resources(path: str = None) -> List[Resource]:
    """
    Load resources from a CSV file.
    Expected columns:
      res_id, name, skills, shift_start_h, shift_end_h, max_hours_per_day
    """
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "resources.csv")
    path = os.path.abspath(path)

    resources = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skills_set = set(s.strip() for s in row["skills"].split("|") if s.strip())
            r = Resource(
                res_id=row["res_id"].strip(),
                name=row.get("name", row["res_id"]).strip(),
                skills=skills_set,
                shift_start_h=int(row["shift_start_h"]),
                shift_end_h=int(row["shift_end_h"]),
                max_hours_per_day=int(row["max_hours_per_day"]),
            )
            resources.append(r)
    return resources


def validate_all_tasks(tasks: List[Task]) -> bool:
    """
    Validate all tasks and print any errors found.
    Returns True if all tasks are valid, False otherwise.
    """
    all_valid = True
    task_ids = {t.task_id for t in tasks}
    for t in tasks:
        errors = t.validate()
        # also check dependency references
        for dep in t.depends_on:
            if dep not in task_ids:
                errors.append(f"[{t.task_id}] depends_on unknown task '{dep}'")
        if errors:
            all_valid = False
            for e in errors:
                print(f"  ✗ VALIDATION ERROR: {e}")
    return all_valid
