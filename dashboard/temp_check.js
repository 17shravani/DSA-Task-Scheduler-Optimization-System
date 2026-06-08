
  /* ═══════════════════════════════════════════════════════════
     STATE MANAGEMENT & DEFAULTS
  ═══════════════════════════════════════════════════════════ */
  const DEFAULT_TASKS = [
    { task_id: "T1", task_name: "Backend API Setup", duration_h: 4, deadline_h: 24, priority: 3, skill: "backend", profit: 80, depends_on: [] },
    { task_id: "T2", task_name: "Frontend UI Design", duration_h: 6, deadline_h: 32, priority: 2, skill: "frontend", profit: 60, depends_on: ["T1"] },
    { task_id: "T3", task_name: "QA Testing Phase 1", duration_h: 2, deadline_h: 20, priority: 5, skill: "qa", profit: 90, depends_on: ["T1"] },
    { task_id: "T4", task_name: "Database Schema", duration_h: 8, deadline_h: 40, priority: 1, skill: "backend", profit: 50, depends_on: [] },
    { task_id: "T5", task_name: "Authentication Module", duration_h: 3, deadline_h: 36, priority: 4, skill: "backend", profit: 70, depends_on: ["T4"] },
    { task_id: "T6", task_name: "Unit Test Suite", duration_h: 4, deadline_h: 48, priority: 3, skill: "qa", profit: 65, depends_on: ["T5"] },
    { task_id: "T7", task_name: "API Documentation", duration_h: 2, deadline_h: 28, priority: 2, skill: "frontend", profit: 45, depends_on: ["T2"] },
    { task_id: "T8", task_name: "Performance Tuning", duration_h: 5, deadline_h: 52, priority: 4, skill: "backend", profit: 85, depends_on: ["T5", "T6"] },
    { task_id: "T9", task_name: "Security Audit", duration_h: 3, deadline_h: 44, priority: 5, skill: "qa", profit: 95, depends_on: ["T3", "T6"] },
    { task_id: "T10", task_name: "Final Integration", duration_h: 6, deadline_h: 60, priority: 3, skill: "frontend", profit: 75, depends_on: ["T7", "T8", "T9"] }
  ];

  const DEFAULT_RESOURCES = [
    { res_id: "R1", name: "Alice", skills: ["backend", "qa"], shift_start_h: 9, shift_end_h: 17, max_hours_per_day: 8 },
    { res_id: "R2", name: "Bob", skills: ["frontend"], shift_start_h: 10, shift_end_h: 18, max_hours_per_day: 8 },
    { res_id: "R3", name: "Carol", skills: ["backend"], shift_start_h: 8, shift_end_h: 16, max_hours_per_day: 8 },
    { res_id: "R4", name: "Dave", skills: ["qa", "frontend"], shift_start_h: 9, shift_end_h: 17, max_hours_per_day: 8 }
  ];

  let tasks = JSON.parse(localStorage.getItem("tasks")) || [...DEFAULT_TASKS];
  let resources = JSON.parse(localStorage.getItem("resources")) || [...DEFAULT_RESOURCES];
  let currentSchedule = null;
  let currentKPIs = null;
  let activeTab = "gantt-tab";
  let backendOnline = false;

  const API_URL = "http://localhost:8000";

  /* Currency helper — reads the dropdown every time (reactive) */
  function getCurrency() {
    const sel = document.getElementById('currency-select');
    return sel ? sel.value : '₹';
  }
  function onCurrencyChange() {
    // Re-render if a schedule is already computed
    if (currentSchedule && currentKPIs) {
      const horizon = parseInt(document.getElementById('horizon-input').value);
      renderAll(currentSchedule, currentKPIs, horizon);
    }
  }

  /* ═══════════════════════════════════════════════════════════
     INIT ON LOAD
  ═══════════════════════════════════════════════════════════ */
  window.onload = function() {
    checkAPIStatus();
    renderEditorTables();
    executeSolver(); // Attempt local solve or server solve immediately
  };

  async function checkAPIStatus() {
    try {
      const resp = await fetch(API_URL);
      if (resp.ok) {
        backendOnline = true;
        const dot = document.getElementById("status-dot");
        dot.className = "status-dot active";
        document.getElementById("status-label").textContent = "API Live (Connected)";
      }
    } catch (e) {
      backendOnline = false;
      const dot = document.getElementById("status-dot");
      dot.className = "status-dot inactive";
      document.getElementById("status-label").textContent = "API Offline (Local Demo Mode)";
    }
  }

  /* ═══════════════════════════════════════════════════════════
     SOLVER EXECUTIONS
  ═══════════════════════════════════════════════════════════ */
  async function executeSolver() {
    const engine = document.getElementById("engine-select").value;
    const objective = document.getElementById("objective-select").value;
    const horizon = parseInt(document.getElementById("horizon-input").value);
    const limit = parseFloat(document.getElementById("limit-input").value);

    // Save current config state
    localStorage.setItem("tasks", JSON.stringify(tasks));
    localStorage.setItem("resources", JSON.stringify(resources));

    if (backendOnline) {
      try {
        const payload = { engine, horizon, objective, time_limit_s: limit, tasks, resources };
        const resp = await fetch(`${API_URL}/solve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        currentSchedule = data.plan;
        currentKPIs = data.kpis;
        renderAll(currentSchedule, currentKPIs, horizon);
        return;
      } catch (e) {
        console.error("Backend error, falling back to local greedy solver:", e);
      }
    }

    // LOCAL GREEDY SOLVER FALLBACK (Error-free client-side rendering)
    runLocalGreedy(horizon);
  }

  async function compareEngines() {
    const horizon = parseInt(document.getElementById("horizon-input").value);
    const limit = parseFloat(document.getElementById("limit-input").value);

    const compArea = document.getElementById("compare-panel-area");
    compArea.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-sec);">⏳ Running comparison solvers...</div>`;
    switchTab("compare-tab");

    if (!backendOnline) {
      // Fully offline: run two greedy variants (different objectives) client-side
      const gPlan = runLocalGreedyForCompare(horizon, "lateness");
      const mPlan = runLocalGreedyForCompare(horizon, "makespan");
      const gKpis = localComputeKPIs(gPlan, horizon);
      const mKpis = localComputeKPIs(mPlan, horizon);
      renderComparison(
        { plan: gPlan, kpis: gKpis, status: "GREEDY (Min-Lateness)" },
        { plan: mPlan, kpis: mKpis, status: "GREEDY (Min-Makespan)" },
        true
      );
      return;
    }

    try {
      const gPayload = { engine: "greedy", horizon, objective: "lateness", time_limit_s: limit, tasks, resources };
      const cPayload = { engine: "cpsat",  horizon, objective: "lateness", time_limit_s: limit, tasks, resources };

      const [gRes, cRes] = await Promise.all([
        fetch(`${API_URL}/solve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(gPayload) }),
        fetch(`${API_URL}/solve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cPayload) })
      ]);

      const gData = await gRes.json();
      let cData   = await cRes.json();

      // If CP-SAT returned an error (e.g. OR-Tools not installed → HTTP 422),
      // fall back to a second greedy run with a different objective so the
      // comparison view still renders without crashing.
      if (!cRes.ok || !cData.kpis) {
        const fallbackPayload = { engine: "greedy", horizon, objective: "makespan", time_limit_s: limit, tasks, resources };
        const fallbackRes  = await fetch(`${API_URL}/solve`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fallbackPayload) });
        cData = await fallbackRes.json();
        cData.status = "GREEDY fallback (CP-SAT unavailable — install ortools)";
        renderComparison(gData, cData, true);
      } else {
        renderComparison(gData, cData, false);
      }
    } catch(e) {
      compArea.innerHTML = `<div class="error-box">⚠️ Comparison failed: ${e.message}<br><small>Tip: make sure the backend is running or use the offline demo.</small></div>`;
    }
  }

  // Standalone greedy run that returns a plan array (used for offline comparison)
  function runLocalGreedyForCompare(horizon) {
    let topoOrder = [];
    try { topoOrder = localTopologicalSort(tasks); }
    catch (e) { return []; }

    const taskLookup = {};
    tasks.forEach(t => taskLookup[t.task_id] = t);
    const resNext = {}; const resDay = {};
    resources.forEach(r => { resNext[r.res_id] = r.shift_start_h; resDay[r.res_id] = 0; });
    const finishTimes = {};
    const plan = [];

    for (const tid of topoOrder) {
      const t = taskLookup[tid];
      const depEnd = t.depends_on.reduce((m, d) => Math.max(m, finishTimes[d] || 0), 0);
      let bestScore = null, bestStart = null, bestResId = null;

      for (const r of resources) {
        if (!r.skills.includes(t.skill)) continue;
        let day = resDay[r.res_id];
        let cur = Math.max(resNext[r.res_id], depEnd, r.shift_start_h + day * 24);
        let fitFound = false;
        for (let attempt = 0; attempt < 15; attempt++) {
          const ss = r.shift_start_h + day * 24, se = r.shift_end_h + day * 24;
          if (cur < ss) cur = ss;
          if (cur + t.duration_h <= se && cur <= horizon) { fitFound = true; break; }
          else { day++; cur = Math.max(resNext[r.res_id], depEnd, r.shift_start_h + day * 24); }
        }
        if (!fitFound || cur + t.duration_h > horizon) continue;
        const endTime = cur + t.duration_h;
        const lateness = Math.max(0, endTime - t.deadline_h);
        const score = lateness * (6 - t.priority) + cur;
        if (bestScore === null || score < bestScore) { bestScore = score; bestStart = cur; bestResId = r.res_id; }
      }

      if (bestStart === null) {
        plan.push({ task_id: tid, task_name: t.task_name, res_id: null, start: null, end: null, lateness: null, on_time: false, missed: true, profit: t.profit, priority: t.priority, deadline_h: t.deadline_h });
        finishTimes[tid] = depEnd;
      } else {
        const endTime = bestStart + t.duration_h;
        const lateness = Math.max(0, endTime - t.deadline_h);
        plan.push({ task_id: tid, task_name: t.task_name, res_id: bestResId, start: bestStart, end: endTime, lateness, on_time: lateness === 0, missed: false, profit: t.profit, priority: t.priority, deadline_h: t.deadline_h });
        finishTimes[tid] = endTime;
        resNext[bestResId] = endTime;
        resDay[bestResId] = Math.floor((endTime - resources.find(r => r.res_id === bestResId).shift_start_h) / 24);
      }
    }
    return plan;
  }

  /* ═══════════════════════════════════════════════════════════
     LOCAL GREEDY ALGORITHM (CLIENT-SIDE)
  ═══════════════════════════════════════════════════════════ */
  function runLocalGreedy(horizon) {
    // 1. Topological Sort using Kahn's algorithm
    let topoOrder = [];
    try {
      topoOrder = localTopologicalSort(tasks);
    } catch (e) {
      alert("Dependency Error: " + e.message);
      return;
    }

    const taskLookup = {};
    tasks.forEach(t => taskLookup[t.task_id] = t);

    // Track resource schedule cursor state
    const resNext = {};
    const resDay = {};
    resources.forEach(r => {
      resNext[r.res_id] = r.shift_start_h;
      resDay[r.res_id] = 0;
    });

    const finishTimes = {};
    const plan = [];

    // 2. Schedule each task topologically
    for (const tid of topoOrder) {
      const t = taskLookup[tid];
      const depEnd = t.depends_on.reduce((maxTime, depId) => {
        return Math.max(maxTime, finishTimes[depId] || 0);
      }, 0);

      let bestScore = null;
      let bestStart = null;
      let bestResId = null;

      for (const r of resources) {
        if (!r.skills.includes(t.skill)) continue; // Skill tag constraint

        let day = resDay[r.res_id];
        let cur = Math.max(resNext[r.res_id], depEnd, r.shift_start_h + day * 24);

        let fitFound = false;
        for (let attempt = 0; attempt < 15; attempt++) {
          const shiftStart = r.shift_start_h + day * 24;
          const shiftEnd = r.shift_end_h + day * 24;

          if (cur < shiftStart) cur = shiftStart;

          if (cur + t.duration_h <= shiftEnd && cur <= horizon) {
            fitFound = true;
            break;
          } else {
            day++;
            cur = Math.max(resNext[r.res_id], depEnd, r.shift_start_h + day * 24);
          }
        }

        if (!fitFound || cur + t.duration_h > horizon) continue;

        const endTime = cur + t.duration_h;
        const lateness = Math.max(0, endTime - t.deadline_h);
        const score = lateness * (6 - t.priority) + cur; // Greedy weight scoring

        if (bestScore === null || score < bestScore) {
          bestScore = score;
          bestStart = cur;
          bestResId = r.res_id;
        }
      }

      if (bestStart === null) {
        plan.push({
          task_id: tid, task_name: t.task_name, res_id: null,
          start: null, end: null, lateness: null,
          on_time: false, missed: true, profit: t.profit, priority: t.priority, deadline_h: t.deadline_h
        });
        finishTimes[tid] = depEnd;
      } else {
        const endTime = bestStart + t.duration_h;
        const lateness = Math.max(0, endTime - t.deadline_h);
        plan.push({
          task_id: tid, task_name: t.task_name, res_id: bestResId,
          start: bestStart, end: endTime, lateness: lateness,
          on_time: lateness === 0, missed: false, profit: t.profit, priority: t.priority, deadline_h: t.deadline_h
        });

        finishTimes[tid] = endTime;
        resNext[bestResId] = endTime;
        resDay[bestResId] = Math.floor((endTime - r.shift_start_h) / 24);
      }
    }

    // Compute KPIs locally
    const kpis = localComputeKPIs(plan, horizon);
    currentSchedule = plan;
    currentKPIs = kpis;
    renderAll(plan, kpis, horizon);
  }

  function localTopologicalSort(taskList) {
    const indegree = {};
    const children = {};
    taskList.forEach(t => {
      indegree[t.task_id] = 0;
      children[t.task_id] = [];
    });

    taskList.forEach(t => {
      t.depends_on.forEach(dep => {
        if (indegree[t.task_id] !== undefined) {
          indegree[t.task_id]++;
          children[dep].push(t.task_id);
        }
      });
    });

    // Heap simulation: sort initial nodes by priority descending
    const queue = taskList.filter(t => indegree[t.task_id] === 0);
    queue.sort((a, b) => b.priority - a.priority || a.deadline_h - b.deadline_h);

    const topo = [];
    while (queue.length > 0) {
      const curr = queue.shift();
      topo.push(curr.task_id);

      children[curr.task_id].forEach(childId => {
        indegree[childId]--;
        if (indegree[childId] === 0) {
          const childObj = taskList.find(t => t.task_id === childId);
          queue.push(childObj);
        }
      });
      queue.sort((a, b) => b.priority - a.priority || a.deadline_h - b.deadline_h);
    }

    if (topo.length !== taskList.length) {
      throw new Error("Cyclic dependencies detected in task configurations!");
    }
    return topo;
  }

  function localComputeKPIs(plan, horizon) {
    let completed = 0;
    let missed = 0;
    let onTime = 0;
    let late = 0;
    let latenessSum = 0;
    let profitSum = 0;
    let missedProfitSum = 0;
    let makespan = 0;
    const util = {};

    resources.forEach(r => util[r.res_id] = 0);

    plan.forEach(p => {
      if (p.missed) {
        missed++;
        missedProfitSum += p.profit;
      } else {
        completed++;
        profitSum += p.profit;
        latenessSum += p.lateness;
        makespan = Math.max(makespan, p.end);
        if (p.on_time) onTime++; else late++;
        util[p.res_id] = (util[p.res_id] || 0) + (p.end - p.start);
      }
    });

    return {
      total_tasks: plan.length,
      completed_tasks: completed,
      missed_tasks: missed,
      on_time_count: onTime,
      late_count: late,
      on_time_pct: plan.length ? Math.round((onTime / plan.length) * 100) : 0,
      total_lateness_h: latenessSum,
      total_profit: profitSum,
      missed_profit: missedProfitSum,
      makespan: makespan,
      utilization_h: util
    };
  }

  /* ═══════════════════════════════════════════════════════════
     RENDER DYNAMIC INTERFACES
  ═══════════════════════════════════════════════════════════ */
  function renderAll(plan, kpis, horizon) {
    // Render KPIs
    document.getElementById("kpi-ontime").textContent = kpis.on_time_pct + "%";
    document.getElementById("kpi-lateness").textContent = kpis.total_lateness_h + "h";
    document.getElementById("kpi-profit").textContent = getCurrency() + kpis.total_profit;
    document.getElementById("kpi-missed").textContent = kpis.missed_tasks;
    document.getElementById("kpi-makespan").textContent = kpis.makespan + "h";

    // Render Gantt
    renderGanttChart(plan, horizon);

    // Render Detailed Table
    renderPlanTable(plan);

    // Render DAG Graph & Critical Path
    renderDAG(plan);
  }

  function renderGanttChart(plan, horizon) {
    const completed = plan.filter(p => !p.missed);
    const missed    = plan.filter(p =>  p.missed);
    const container = document.getElementById("gantt-area");

    if (completed.length === 0) {
      container.innerHTML = `<p style="color:var(--text-muted);padding:40px 0;text-align:center;">No completed tasks yet — click ⚡ Optimize to generate a schedule.</p>`;
      return;
    }

    const endBound = Math.max(...completed.map(p => p.end), horizon);
    const tickStep = endBound <= 48 ? 4 : endBound <= 96 ? 8 : 24;

    /* ── Ruler ticks ── */
    let ticksHTML = '';
    for (let h = 0; h <= endBound; h += tickStep) {
      const lp = (h / endBound * 100).toFixed(2);
      const isDay = h % 24 === 0;
      const label = isDay ? (h === 0 ? 'Start' : 'Day ' + (h / 24)) : h + 'h';
      ticksHTML += `<div class="gantt-hour-tick${isDay ? ' day-tick' : ''}" style="left:${lp}%">${label}</div>`;
    }

    /* ── Shared grid-lines HTML (injected into every track) ── */
    let gridHTML = '';
    for (let h = 0; h <= endBound; h += tickStep) {
      const lp = (h / endBound * 100).toFixed(2);
      const isDay = h % 24 === 0;
      gridHTML += `<div class="gantt-grid-line${isDay ? ' day-line' : ''}" style="left:${lp}%"></div>`;
    }

    /* ── Build one row per resource ── */
    let rowsHTML = '';
    resources.forEach(r => {
      const rTasks = completed.filter(p => p.res_id === r.res_id);
      let inner = gridHTML;

      /* Shift-window tint for every day */
      for (let day = 0; day * 24 <= endBound + 24; day++) {
        const ss = r.shift_start_h + day * 24;
        const se = r.shift_end_h   + day * 24;
        if (ss >= endBound) break;
        const sp = (Math.min(ss, endBound) / endBound * 100).toFixed(2);
        const wp = ((Math.min(se, endBound) - Math.min(ss, endBound)) / endBound * 100).toFixed(2);
        inner += `<div class="gantt-shift-window" style="left:${sp}%;width:${wp}%"></div>`;
      }

      /* Task bars */
      rTasks.forEach(p => {
        const sp  = (p.start / endBound * 100).toFixed(2);
        const wp  = ((p.end - p.start) / endBound * 100).toFixed(2);
        const col = `t-col-${(parseInt(p.task_id.replace(/\D/g,'')) % 8) || 1}`;
        const lateShadow = !p.on_time
          ? 'box-shadow:inset 0 0 0 2px var(--amber),0 0 10px rgba(245,158,11,0.35);'
          : '';
        const wFloat = parseFloat(wp);
        const labelTxt = wFloat > 8
          ? `${p.task_id}: ${p.task_name}`
          : wFloat > 3 ? p.task_id : '';
        const tip = `${p.task_id} — ${p.task_name}|⏱ ${p.start}h → ${p.end}h  (${p.end - p.start}h)|📅 Deadline: ${p.deadline_h}h  Lateness: ${p.lateness}h|💰 Profit: ${getCurrency()}${p.profit}  Priority: ${p.priority}`;

        inner += `<div class="gantt-task-bar ${col}" style="left:${sp}%;width:${wp}%;${lateShadow}"
          onclick="loadTaskToForm('${p.task_id}')" data-tip="${tip}">
          <span class="gantt-bar-label">${labelTxt}</span>
        </div>`;
      });

      /* Deadline markers */
      rTasks.forEach(p => {
        if (p.deadline_h && p.deadline_h <= endBound) {
          const dp = (p.deadline_h / endBound * 100).toFixed(2);
          inner += `<div class="gantt-dl-marker" style="left:${dp}%" title="Deadline: ${p.task_id}"></div>`;
        }
      });

      const skillTags = r.skills.map(s => `<span class="skill-tag">${s}</span>`).join('');
      rowsHTML += `
        <div class="gantt-grid-row">
          <div class="gantt-resource-name">
            <div class="res-name-main">${r.name}</div>
            <div class="res-name-skills">${skillTags}</div>
          </div>
          <div class="gantt-track">${inner}</div>
        </div>`;
    });

    /* ── Missed-tasks strip ── */
    const missedHTML = missed.length ? `
      <div class="gantt-missed-strip">
        ⚠️ <strong>Missed / Unscheduled:</strong>
        ${missed.map(m => `<span class="missed-tag">${m.task_id}: ${m.task_name}</span>`).join('')}
      </div>` : '';

    /* ── Legend ── */
    const legendHTML = `
      <div class="gantt-legend">
        <span style="font-weight:700;color:var(--text-primary);">Legend:</span>
        <div class="legend-item"><div class="legend-box" style="background:rgba(79,110,247,0.12);border:1px solid rgba(79,110,247,0.3);"></div>Shift window</div>
        <div class="legend-item"><div class="legend-box t-col-1"></div>Scheduled task</div>
        <div class="legend-item"><div class="legend-box" style="background:rgba(255,255,255,0.08);border:2px solid var(--amber);"></div>Late task</div>
        <div class="legend-item"><div class="legend-box" style="background:#ef4444;width:4px;height:14px;"></div>Deadline marker</div>
        <div class="legend-item" style="margin-left:auto;font-size:0.7rem;color:var(--text-muted);">💡 Hover bar for details • Click to edit</div>
      </div>`;

    container.innerHTML = `
      <div class="gantt-container">
        <div class="gantt-header-row">
          <div class="gantt-res-col">Resource</div>
          <div class="gantt-timeline-col">${ticksHTML}</div>
        </div>
        ${rowsHTML}
      </div>
      ${missedHTML}
      ${legendHTML}
      <div id="gantt-tooltip" class="gantt-tooltip"></div>`;

    /* ── Tooltip interaction ── */
    const tooltip = document.getElementById('gantt-tooltip');
    container.querySelectorAll('.gantt-task-bar[data-tip]').forEach(bar => {
      bar.addEventListener('mouseenter', () => {
        tooltip.innerHTML = bar.getAttribute('data-tip')
          .split('|').map(l => `<div>${l}</div>`).join('');
        tooltip.classList.add('visible');
      });
      bar.addEventListener('mousemove', e => {
        tooltip.style.left = (e.clientX + 16) + 'px';
        tooltip.style.top  = (e.clientY - 10) + 'px';
      });
      bar.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
    });
  }

  function renderPlanTable(plan) {
    const sorted = [...plan].sort((a,b) => {
      if (a.missed && !b.missed) return 1;
      if (!a.missed && b.missed) return -1;
      return (a.start || 0) - (b.start || 0);
    });

    const rows = sorted.map(p => {
      if (p.missed) {
        return `
          <tr>
            <td class="mono" style="color:var(--red); font-weight:700;">${p.task_id}</td>
            <td>${p.task_name}</td>
            <td>—</td>
            <td>—</td>
            <td class="mono">${p.deadline_h}h</td>
            <td>—</td>
            <td><span class="status-badge status-missed">Missed</span></td>
            <td>${p.priority}</td>
            <td style="color:var(--red); font-weight:700;">${getCurrency()}${p.profit}</td>
          </tr>
        `;
      }
      const badge = p.on_time 
        ? `<span class="status-badge status-on-time">On-Time</span>`
        : `<span class="status-badge status-late">Late (+${p.lateness}h)</span>`;
      
      const resName = resources.find(r => r.res_id === p.res_id)?.name || p.res_id;

      return `
        <tr>
          <td class="mono" style="color:var(--accent); font-weight:700;">${p.task_id}</td>
          <td>${p.task_name}</td>
          <td><span style="color:var(--purple-dim); color:#c4b5fd; font-weight:700;">${resName}</span></td>
          <td class="mono">${p.start}h</td>
          <td class="mono">${p.end}h</td>
          <td class="mono">${p.lateness}h</td>
          <td>${badge}</td>
          <td>${p.priority}</td>
          <td style="color:var(--green); font-weight:700;">${getCurrency()}${p.profit}</td>
        </tr>
      `;
    }).join("");

    document.getElementById("table-area").innerHTML = `
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Task Name</th>
            <th>Assigned Resource</th>
            <th>Start Time</th>
            <th>End Time</th>
            <th>Lateness</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Profit</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    `;
  }

  /* ═══════════════════════════════════════════════════════════
     DAG INTERACTIVE VISUALIZER & CPM (CRITICAL PATH)
  ═══════════════════════════════════════════════════════════ */
  function renderDAG(plan) {
    const dagArea = document.getElementById("dag-area");
    const svg = document.getElementById("dag-svg");
    svg.innerHTML = ""; // Clear arrows

    // 1. Calculate ES, EF, LS, LF using CPM to find Critical Path
    const cpm = calculateCriticalPath(tasks);

    // Filter elements except canvas
    const nodes = dagArea.querySelectorAll(".dag-node");
    nodes.forEach(n => n.remove());

    // 2. Compute topological layers (X position groups)
    const layers = {};
    const nodeDepths = {};

    function getDepth(tid) {
      if (nodeDepths[tid] !== undefined) return nodeDepths[tid];
      const t = tasks.find(x => x.task_id === tid);
      if (!t || t.depends_on.length === 0) {
        nodeDepths[tid] = 0;
        return 0;
      }
      const depths = t.depends_on.map(dep => getDepth(dep));
      const d = 1 + Math.max(...depths);
      nodeDepths[tid] = d;
      return d;
    }

    tasks.forEach(t => {
      const depth = getDepth(t.task_id);
      if (!layers[depth]) layers[depth] = [];
      layers[depth].push(t.task_id);
    });

    const maxLayer = Math.max(...Object.keys(layers).map(Number), 0);
    const dagWidth = dagArea.clientWidth;
    const dagHeight = dagArea.clientHeight;

    const layerWidth = dagWidth / (maxLayer + 2);
    const nodePositions = {};

    // 3. Position and create HTML divs for nodes
    Object.keys(layers).forEach(layerStr => {
      const layer = parseInt(layerStr);
      const layerTasks = layers[layer];
      const numNodes = layerTasks.length;

      layerTasks.forEach((tid, idx) => {
        const x = layerWidth * (layer + 0.6);
        const y = (dagHeight / (numNodes + 1)) * (idx + 1);

        nodePositions[tid] = { x, y };

        const t = tasks.find(n => n.task_id === tid);
        const isCritical = cpm.criticalNodes.includes(tid);
        const criticalClass = isCritical ? "critical" : "";

        const div = document.createElement("div");
        div.className = `dag-node ${criticalClass}`;
        div.style.left = `${x - 50}px`;
        div.style.top = `${y - 24}px`;
        div.setAttribute("onclick", `loadTaskToForm('${tid}')`);
        div.innerHTML = `
          <span class="node-id">${tid}</span>
          <span class="node-name">${t.task_name}</span>
        `;
        dagArea.appendChild(div);
      });
    });

    // 4. Render connecting SVG lines (arrows)
    let arrowsHTML = `
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" fill="rgba(255,255,255,0.25)" />
        </marker>
        <marker id="arrow-crit" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--red)" />
        </marker>
      </defs>
    `;

    tasks.forEach(t => {
      t.depends_on.forEach(depId => {
        const startPos = nodePositions[depId];
        const endPos = nodePositions[t.task_id];

        if (startPos && endPos) {
          const isCritEdge = cpm.criticalNodes.includes(depId) && cpm.criticalNodes.includes(t.task_id);
          const color = isCritEdge ? "var(--red)" : "rgba(255,255,255,0.18)";
          const strokeWidth = isCritEdge ? "3" : "1.5";
          const marker = isCritEdge ? "url(#arrow-crit)" : "url(#arrow)";

          arrowsHTML += `
            <line x1="${startPos.x}" y1="${startPos.y}" x2="${endPos.x - 52}" y2="${endPos.y}" stroke="${color}" stroke-width="${strokeWidth}" marker-end="${marker}" />
          `;
        }
      });
    });

    svg.innerHTML = arrowsHTML;

    // Render critical path list
    const cpathContainer = document.getElementById("cpath-flow-area");
    cpathContainer.innerHTML = cpm.criticalNodes.map(tid => `<span class="cpath-node">${tid}</span>`).join(" ➔ ");
  }

  function calculateCriticalPath(taskList) {
    const n = taskList.length;
    if (n === 0) return { criticalNodes: [] };

    const lookup = {};
    taskList.forEach(t => lookup[t.task_id] = t);

    // Calculate topological order
    const topo = localTopologicalSort(taskList);

    // Forward pass (Early times)
    const ES = {};
    const EF = {};
    topo.forEach(tid => {
      const t = lookup[tid];
      const maxDepEF = t.depends_on.reduce((maxVal, depId) => Math.max(maxVal, EF[depId] || 0), 0);
      ES[tid] = maxDepEF;
      EF[tid] = maxDepEF + t.duration_h;
    });

    // Backward pass (Late times)
    const LS = {};
    const LF = {};
    const maxProjectTime = Math.max(...Object.values(EF), 0);

    topo.slice().reverse().forEach(tid => {
      const t = lookup[tid];
      // Find downstream tasks that depend on this task
      const downstream = taskList.filter(x => x.depends_on.includes(tid));
      
      let minLS = maxProjectTime;
      if (downstream.length > 0) {
        minLS = Math.min(...downstream.map(x => LS[x.task_id]));
      }

      LF[tid] = minLS;
      LS[tid] = minLS - t.duration_h;
    });

    // Critical nodes have slack = 0
    const criticalNodes = topo.filter(tid => {
      const slack = LS[tid] - ES[tid];
      return Math.abs(slack) < 0.01;
    });

    return { ES, EF, LS, LF, criticalNodes };
  }

  /* ═══════════════════════════════════════════════════════════
     COMPARE VIEW RENDER
  ═══════════════════════════════════════════════════════════ */
  function renderComparison(gData, cData, isFallback) {
    const compArea = document.getElementById("compare-panel-area");

    // Guard: ensure both KPI objects are valid
    if (!gData || !gData.kpis || !cData || !cData.kpis) {
      compArea.innerHTML = `<div class="error-box">⚠️ Could not load comparison data. Please click Optimize first, then Compare.</div>`;
      return;
    }

    const formatDelta = (a, b, unit="", higherBetter=true, prefix="") => {
      const d = b - a;
      if (d === 0) return `<span style="color:var(--text-sec)">${prefix}0${unit} (Equal)</span>`;
      const isGood = higherBetter ? d > 0 : d < 0;
      const color = isGood ? "var(--green)" : "var(--red)";
      const sign = d > 0 ? "+" : "-";
      const absD = Math.abs(d);
      return `<span style="color:${color}">${sign}${prefix}${absD}${unit}</span>`;
    };

    const gk = gData.kpis;
    const ck = cData.kpis;
    const gLabel = isFallback ? "⚡ Greedy (Min-Lateness)" : "⚡ Greedy Heuristic";
    const cLabel = isFallback ? "⚡ Greedy (Min-Makespan)" : "🔬 CP-SAT Optimal";

    const fallbackBanner = isFallback ? `
      <div style="background:rgba(245,158,11,0.1); border:1px solid var(--amber); border-radius:var(--radius); padding:12px 18px; margin-bottom:16px; font-size:0.83rem; color:#fde68a;">
        ⚠️ <strong>CP-SAT solver not available</strong> (OR-Tools not installed). Showing two Greedy variants instead:
        <strong>Min-Lateness</strong> vs <strong>Min-Makespan</strong>.
        To enable CP-SAT, run: <code style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px;">pip install ortools</code>
      </div>` : "";

    compArea.innerHTML = `
      ${fallbackBanner}
      <div class="compare-grid">
        <div class="compare-side-card">
          <div class="compare-side-title">${gLabel}</div>
          <table style="margin-top:10px;">
            <tr><td>On-Time %</td><td class="mono">${gk.on_time_pct}%</td></tr>
            <tr><td>Total Lateness</td><td class="mono">${gk.total_lateness_h}h</td></tr>
            <tr><td>Total Profit</td><td class="mono">${getCurrency()}${gk.total_profit}</td></tr>
            <tr><td>Makespan</td><td class="mono">${gk.makespan}h</td></tr>
            <tr><td>Missed Tasks</td><td class="mono">${gk.missed_tasks}</td></tr>
          </table>
        </div>

        <div class="compare-side-card">
          <div class="compare-side-title">${cLabel}</div>
          <table style="margin-top:10px;">
            <tr><td>On-Time %</td><td class="mono">${ck.on_time_pct}%</td></tr>
            <tr><td>Total Lateness</td><td class="mono">${ck.total_lateness_h}h</td></tr>
            <tr><td>Total Profit</td><td class="mono">${getCurrency()}${ck.total_profit}</td></tr>
            <tr><td>Makespan</td><td class="mono">${ck.makespan}h</td></tr>
            <tr><td>Missed Tasks</td><td class="mono">${ck.missed_tasks}</td></tr>
          </table>
        </div>
      </div>

      <div class="glass-card" style="margin-top:20px; background:rgba(255,255,255,0.01);">
        <div class="card-title">⚖️ Side-by-Side KPI Comparison</div>
        <table style="margin-top:14px;">
          <thead>
            <tr>
              <th>KPI Metric</th>
              <th>${gLabel}</th>
              <th>${cLabel}</th>
              <th>Δ Delta</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>On-Time Percentage</td>
              <td class="mono">${gk.on_time_pct}%</td>
              <td class="mono">${ck.on_time_pct}%</td>
              <td>${formatDelta(gk.on_time_pct, ck.on_time_pct, "%", true)}</td>
            </tr>
            <tr>
              <td>Total Scheduling Lateness</td>
              <td class="mono">${gk.total_lateness_h}h</td>
              <td class="mono">${ck.total_lateness_h}h</td>
              <td>${formatDelta(gk.total_lateness_h, ck.total_lateness_h, "h", false)}</td>
            </tr>
            <tr>
              <td>Realized Project Profit</td>
              <td class="mono">${getCurrency()}${gk.total_profit}</td>
              <td class="mono">${getCurrency()}${ck.total_profit}</td>
              <td>${formatDelta(gk.total_profit, ck.total_profit, "", true, getCurrency())}</td>
            </tr>
            <tr>
              <td>Makespan Length</td>
              <td class="mono">${gk.makespan}h</td>
              <td class="mono">${ck.makespan}h</td>
              <td>${formatDelta(gk.makespan, ck.makespan, "h", false)}</td>
            </tr>
            <tr>
              <td>Missed Tasks</td>
              <td class="mono">${gk.missed_tasks}</td>
              <td class="mono">${ck.missed_tasks}</td>
              <td>${formatDelta(gk.missed_tasks, ck.missed_tasks, "", false)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    `;
  }

  /* ═══════════════════════════════════════════════════════════
     EDITORS TABLES & FORMS (NEW DYNAMIC CONFIGURATORS)
   ═══════════════════════════════════════════════════════════ */
  function renderEditorTables() {
    // Tasks table render
    const tBody = document.getElementById("editor-tasks-table");
    tBody.innerHTML = tasks.map(t => {
      const deps = t.depends_on.length > 0 ? t.depends_on.join(", ") : "—";
      return `
        <tr>
          <td class="mono" style="color:var(--accent);">${t.task_id}</td>
          <td>${t.task_name}</td>
          <td class="mono">${t.duration_h}h</td>
          <td class="mono">${t.deadline_h}h</td>
          <td>${t.priority}</td>
          <td><span class="badge badge-purple" style="padding:2px 8px; font-size:0.68rem;">${t.skill}</span></td>
          <td style="color:var(--green); font-weight:700;">${getCurrency()}${t.profit}</td>back ? "⚡ Greedy (Min-Lateness)" : "⚡ Greedy Heuristic";
    const cLabel = isFallback ? "⚡ Greedy (Min-Makespan)" : "🔬 CP-SAT Optimal";

    const fallbackBanner = isFallback ? `
      <div style="background:rgba(245,158,11,0.1); border:1px solid var(--amber); border-radius:var(--radius); padding:12px 18px; margin-bottom:16px; font-size:0.83rem; color:#fde68a;">
        ⚠️ <strong>CP-SAT solver not available</strong> (OR-Tools not installed). Showing two Greedy variants instead:
        <strong>Min-Lateness</strong> vs <strong>Min-Makespan</strong>.
        To enable CP-SAT, run: <code style="background:rgba(0,0,0,0.3); padding:2px 6px; border-radius:4px;">pip install ortools</code>
      </div>` : "";

    compArea.innerHTML = `
      ${fallbackBanner}
      <div class="compare-grid">
        <div class="compare-side-card">
          <div class="compare-side-title">${gLabel}</div>
          <table style="margin-top:10px;">
            <tr><td>On-Time %</td><td class="mono">${gk.on_time_pct}%</td></tr>
            <tr><td>Total Lateness</td><td class="mono">${gk.total_lateness_h}h</td></tr>
            <tr><td>Total Profit</td><td class="mono">$${gk.total_profit}</td></tr>
            <tr><td>Makespan</td><td class="mono">${gk.makespan}h</td></tr>
            <tr><td>Missed Tasks</td><td class="mono">${gk.missed_tasks}</td></tr>
          </table>
        </div>

        <div class="compare-side-card">
          <div class="compare-side-title">${cLabel}</div>
          <table style="margin-top:10px;">
            <tr><td>On-Time %</td><td class="mono">${ck.on_time_pct}%</td></tr>
            <tr><td>Total Lateness</td><td class="mono">${ck.total_lateness_h}h</td></tr>
            <tr><td>Total Profit</td><td class="mono">$${ck.total_profit}</td></tr>
            <tr><td>Makespan</td><td class="mono">${ck.makespan}h</td></tr>
            <tr><td>Missed Tasks</td><td class="mono">${ck.missed_tasks}</td></tr>
          </table>
        </div>
      </div>

      <div class="glass-card" style="margin-top:20px; background:rgba(255,255,255,0.01);">
        <div class="card-title">⚖️ Side-by-Side KPI Comparison</div>
        <table style="margin-top:14px;">
          <thead>
            <tr>
              <th>KPI Metric</th>
              <th>${gLabel}</th>
              <th>${cLabel}</th>
              <th>Δ Delta</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>On-Time Percentage</td>
              <td class="mono">${gk.on_time_pct}%</td>
              <td class="mono">${ck.on_time_pct}%</td>
              <td>${formatDelta(gk.on_time_pct, ck.on_time_pct, "%", true)}</td>
            </tr>
            <tr>
              <td>Total Scheduling Lateness</td>
              <td class="mono">${gk.total_lateness_h}h</td>
              <td class="mono">${ck.total_lateness_h}h</td>
              <td>${formatDelta(gk.total_lateness_h, ck.total_lateness_h, "h", false)}</td>
            </tr>
            <tr>
              <td>Realized Project Profit</td>
              <td class="mono">$${gk.total_profit}</td>
              <td class="mono">$${ck.total_profit}</td>
              <td>${formatDelta(gk.total_profit, ck.total_profit, "", true)}</td>
            </tr>
            <tr>
              <td>Makespan Length</td>
              <td class="mono">${gk.makespan}h</td>
              <td class="mono">${ck.makespan}h</td>
              <td>${formatDelta(gk.makespan, ck.makespan, "h", false)}</td>
            </tr>
            <tr>
              <td>Missed Tasks</td>
              <td class="mono">${gk.missed_tasks}</td>
              <td class="mono">${ck.missed_tasks}</td>
              <td>${formatDelta(gk.missed_tasks, ck.missed_tasks, "", false)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    `;
  }

  /* ═══════════════════════════════════════════════════════════
     EDITORS TABLES & FORMS (NEW DYNAMIC CONFIGURATORS)
  ═══════════════════════════════════════════════════════════ */
  function renderEditorTables() {
    // Tasks table render
    const tBody = document.getElementById("editor-tasks-table");
    tBody.innerHTML = tasks.map(t => {
      const deps = t.depends_on.length > 0 ? t.depends_on.join(", ") : "—";
      return `
        <tr>
          <td class="mono" style="color:var(--accent);">${t.task_id}</td>
          <td>${t.task_name}</td>
          <td class="mono">${t.duration_h}h</td>
          <td class="mono">${t.deadline_h}h</td>
          <td>${t.priority}</td>
          <td><span class="badge badge-purple" style="padding:2px 8px; font-size:0.68rem;">${t.skill}</span></td>
          <td style="color:var(--green); font-weight:700;">$${t.profit}</td>
          <td class="mono">${deps}</td>
          <td>
            <button class="btn btn-sec" style="padding:4px 8px; font-size:0.7rem; display:inline-block;" onclick="loadTaskToForm('${t.task_id}')">✍️ Edit</button>
            <button class="btn btn-danger" style="padding:4px 8px; font-size:0.7rem; display:inline-block; margin-top:2px;" onclick="deleteTask('${t.task_id}')">🗑️ Del</button>
          </td>
        </tr>
      `;
    }).join("");

    // Resources table render
    const rBody = document.getElementById("editor-resources-table");
    rBody.innerHTML = resources.map(r => {
      return `
        <tr>
          <td class="mono">${r.res_id}</td>
          <td><strong>${r.name}</strong></td>
          <td>${r.skills.map(sk => `<span class="badge badge-blue" style="padding:2px 8px; font-size:0.68rem;">${sk}</span>`).join(" ")}</td>
          <td class="mono">${r.shift_start_h}:00</td>
          <td class="mono">${r.shift_end_h}:00</td>
          <td class="mono">${r.max_hours_per_day}h/day</td>
          <td>
            <button class="btn btn-sec" style="padding:4px 8px; font-size:0.7rem; display:inline-block;" onclick="loadResourceToForm('${r.res_id}')">✍️ Edit</button>
            <button class="btn btn-danger" style="padding:4px 8px; font-size:0.7rem; display:inline-block; margin-top:2px;" onclick="deleteResource('${r.res_id}')">🗑️ Del</button>
          </td>
        </tr>
      `;
    }).join("");
  }

  // Task Actions
  function loadTaskToForm(tid) {
    const t = tasks.find(x => x.task_id === tid);
    if (!t) return;
    document.getElementById("form-task-title").textContent = `✍️ Edit Task ${t.task_id}`;
    document.getElementById("form-task-id").value = t.task_id;
    document.getElementById("form-task-id").disabled = true;
    document.getElementById("form-task-name").value = t.task_name;
    document.getElementById("form-task-dur").value = t.duration_h;
    document.getElementById("form-task-ddl").value = t.deadline_h;
    document.getElementById("form-task-prio").value = t.priority;
    document.getElementById("form-task-skill").value = t.skill;
    document.getElementById("form-task-profit").value = t.profit;
    document.getElementById("form-task-deps").value = t.depends_on.join(", ");
    
    // Switch to task tab in layout automatically
    switchSubTab('tasks');
  }

  function saveTask() {
    const tid = document.getElementById("form-task-id").value.trim();
    const name = document.getElementById("form-task-name").value.trim();
    const dur = parseInt(document.getElementById("form-task-dur").value);
    const ddl = parseInt(document.getElementById("form-task-ddl").value);
    const prio = parseInt(document.getElementById("form-task-prio").value);
    const skill = document.getElementById("form-task-skill").value;
    const profit = parseInt(document.getElementById("form-task-profit").value);
    const depsStr = document.getElementById("form-task-deps").value;
    const deps = depsStr.split(",").map(d => d.trim()).filter(d => d.length > 0);

    if (!tid || !name) {
      alert("Please fill in Task ID and Task Name.");
      return;
    }

    const tObj = { task_id: tid, task_name: name, duration_h: dur, deadline_h: ddl, priority: prio, skill, profit, depends_on: deps };

    const idx = tasks.findIndex(x => x.task_id === tid);
    if (idx !== -1) {
      tasks[idx] = tObj; // Update
    } else {
      tasks.push(tObj); // Insert new
    }

    clearTaskForm();
    renderEditorTables();
    executeSolver();
  }

  function deleteTask(tid) {
    // Check if other tasks depend on this task
    const dependents = tasks.filter(t => t.depends_on.includes(tid));
    if (dependents.length > 0) {
      alert(`Cannot delete task ${tid} because other tasks depend on it: ${dependents.map(d => d.task_id).join(", ")}`);
      return;
    }

    tasks = tasks.filter(t => t.task_id !== tid);
    renderEditorTables();
    executeSolver();
  }

  function clearTaskForm() {
    document.getElementById("form-task-title").textContent = "➕ Add New Task";
    document.getElementById("form-task-id").value = "T" + (tasks.length + 1);
    document.getElementById("form-task-id").disabled = false;
    document.getElementById("form-task-name").value = "New Hotfix QA Node";
    document.getElementById("form-task-dur").value = "3";
    document.getElementById("form-task-ddl").value = "48";
    document.getElementById("form-task-prio").value = "3";
    document.getElementById("form-task-profit").value = "70";
    document.getElementById("form-task-deps").value = "";
  }

  // Resource Actions
  function loadResourceToForm(rid) {
    const r = resources.find(x => x.res_id === rid);
    if (!r) return;
    document.getElementById("form-res-title").textContent = `✍️ Edit Resource ${r.res_id}`;
    document.getElementById("form-res-id").value = r.res_id;
    document.getElementById("form-res-id").disabled = true;
    document.getElementById("form-res-name").value = r.name;
    document.getElementById("form-res-skills").value = r.skills.join(", ");
    document.getElementById("form-res-start").value = r.shift_start_h;
    document.getElementById("form-res-end").value = r.shift_end_h;
    document.getElementById("form-res-cap").value = r.max_hours_per_day;

    switchSubTab('resources');
  }

  function saveResource() {
    const rid = document.getElementById("form-res-id").value.trim();
    const name = document.getElementById("form-res-name").value.trim();
    const skillsStr = document.getElementById("form-res-skills").value.trim();
    const skills = skillsStr.split(",").map(sk => sk.trim()).filter(sk => sk.length > 0);
    const start = parseInt(document.getElementById("form-res-start").value);
    const end = parseInt(document.getElementById("form-res-end").value);
    const cap = parseInt(document.getElementById("form-res-cap").value);

    if (!rid || !name || skills.length === 0) {
      alert("Please specify Resource ID, Name, and Skills.");
      return;
    }

    const rObj = { res_id: rid, name, skills, shift_start_h: start, shift_end_h: end, max_hours_per_day: cap };

    const idx = resources.findIndex(x => x.res_id === rid);
    if (idx !== -1) {
      resources[idx] = rObj;
    } else {
      resources.push(rObj);
    }

    clearResourceForm();
    renderEditorTables();
    executeSolver();
  }

  function deleteResource(rid) {
    if (resources.length <= 1) {
      alert("At least one resource must exist in the planner system.");
      return;
    }
    resources = resources.filter(r => r.res_id !== rid);
    renderEditorTables();
    executeSolver();
  }

  function clearResourceForm() {
    document.getElementById("form-res-title").textContent = "➕ Add Resource";
    document.getElementById("form-res-id").value = "R" + (resources.length + 1);
    document.getElementById("form-res-id").disabled = false;
    document.getElementById("form-res-name").value = "New Engineer";
    document.getElementById("form-res-skills").value = "backend";
    document.getElementById("form-res-start").value = "9";
    document.getElementById("form-res-end").value = "17";
    document.getElementById("form-res-cap").value = "8";
  }

  // Subtab switching
  function switchSubTab(tab) {
    document.getElementById("subtab-tasks").style.display = tab === 'tasks' ? 'block' : 'none';
    document.getElementById("subtab-resources").style.display = tab === 'resources' ? 'block' : 'none';
    
    document.getElementById("btn-subtab-tasks").className = tab === 'tasks' ? 'tab-btn active' : 'tab-btn';
    document.getElementById("btn-subtab-resources").className = tab === 'resources' ? 'tab-btn active' : 'tab-btn';
  }

  function resetToCSVDefault() {
    if (confirm("Resetting will discard all current edits. Proceed?")) {
      tasks = [...DEFAULT_TASKS];
      resources = [...DEFAULT_RESOURCES];
      localStorage.clear();
      renderEditorTables();
      executeSolver();
    }
  }

  function exportDataJSON() {
    const payload = { tasks, resources };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "scheduler_configuration.json"; a.click();
    URL.revokeObjectURL(url);
  }

  /* ═══════════════════════════════════════════════════════════
     EXPORT PLAN TO CSV
  ═══════════════════════════════════════════════════════════ */
  function exportScheduleCSV() {
    if (!currentSchedule) return;
    const headers = ["task_id", "task_name", "res_id", "start", "end", "lateness", "on_time", "missed", "profit", "priority"];
    const rows = currentSchedule.map(p => headers.map(h => p[h] ?? "").join(","));
    const csvContent = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "optimized_scheduler_report.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  /* ═══════════════════════════════════════════════════════════
     TAB BAR NAVIGATION
  ═══════════════════════════════════════════════════════════ */
  function switchTab(tabId) {
    activeTab = tabId;
    const tabs = document.querySelectorAll(".tab-content");
    tabs.forEach(t => t.classList.remove("active"));
    document.getElementById(tabId).classList.add("active");

    const buttons = document.querySelectorAll(".tab-bar .tab-btn");
    buttons.forEach(b => b.classList.remove("active"));
    
    // Set active button
    event.currentTarget.classList.add("active");

    if (tabId === "dag-tab") {
      setTimeout(() => renderDAG(currentSchedule), 50); // Small delay for rendering widths
    }
  }
