// Отрисовка разбора диалога и плеер курсов — общие для кабинетов РОПа и сотрудника.

const OnvyUI = (() => {
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // --- Модалка ---
  function ensureOverlay() {
    let ov = document.getElementById("onvyOverlay");
    if (!ov) {
      ov = document.createElement("div");
      ov.id = "onvyOverlay";
      ov.className = "overlay";
      ov.innerHTML = '<div class="modal"><button class="close">✕</button><div id="onvyModalBody"></div></div>';
      document.body.appendChild(ov);
      ov.querySelector(".close").onclick = () => ov.classList.remove("open");
      ov.addEventListener("click", (e) => { if (e.target === ov) ov.classList.remove("open"); });
    }
    return ov;
  }
  function openModal(html) {
    const ov = ensureOverlay();
    ov.querySelector("#onvyModalBody").innerHTML = html;
    ov.classList.add("open");
    return ov.querySelector("#onvyModalBody");
  }

  // --- Разбор диалога ---
  const KPI_COLOR = (v) => (v >= 70 ? "var(--good)" : v >= 40 ? "var(--warn)" : "var(--bad)");
  const ST_ICON = { success: "✓", warning: "!", fail: "✕" };
  const ST_TEXT = { success: "ок", warning: "частично", fail: "провал" };

  function analysisHtml(d) {
    const a = d.analysis || {};
    const deal = a.deal_analysis || {};
    const kpi = d.kpi_score ?? a.kpi_score ?? 0;
    const s = a.sentiment || {};
    const pos = +s.positive || 0, neu = +s.neutral || 0, neg = +s.negative || 0;

    const dealPill = deal.is_sold
      ? `<span class="pill on">💰 Продажа${deal.detected_amount ? " · " + deal.detected_amount + "₽" : ""}</span>`
      : '<span class="pill off">Без продажи</span>';

    const compliance = (a.script_compliance || []).map((c) =>
      `<div class="st ${esc(c.status)}"><span class="ic">${ST_ICON[c.status] || "?"}</span>${esc(c.label)} <span class="muted small">— ${ST_TEXT[c.status] || c.status}</span></div>`
    ).join("");

    const list = (items, icon) => (items || []).map((x) => `<div class="log-item">${icon} ${esc(x)}</div>`).join("");

    const fixes = (a.mistakes_and_fixes || []).map((m) =>
      `<div class="log-item"><div><b style="color:var(--bad)">Ошибка:</b> ${esc(m.error)}</div>
       <div style="margin-top:4px"><b style="color:var(--good)">Как надо:</b> «${esc(m.fix)}»</div></div>`
    ).join("");

    const fillers = (a.filler_words || []).map((f) => `<span class="pill warn">${esc(f.word)} ×${f.count}</span>`).join(" ");

    const chat = (a.transcript_parsed || []).map((r) => {
      const cls = r.speaker === "Клиент" ? "cli" : "emp";
      const tags = (r.tags || []).map((t) => `<span class="pill">${esc(t)}</span>`).join(" ");
      return `<div class="msg ${cls}"><div class="who">${esc(r.speaker)} ${r.time ? "· " + esc(r.time) : ""} ${tags}</div>${esc(r.text)}</div>`;
    }).join("");

    return `
      <div class="spread" style="margin-bottom:10px">
        <div class="kpiring" style="background:conic-gradient(${KPI_COLOR(kpi)} ${kpi * 3.6}deg, #eeedf7 0)">
          <div class="inner"><div class="num">${kpi}</div><div class="cap">KPI</div></div>
        </div>
        <div style="flex:1;margin-left:14px">
          <div>${dealPill}</div>
          <p style="margin:8px 0 0;font-size:14.5px">${esc(a.summary || "")}</p>
        </div>
      </div>

      <h2 class="sec">Тон диалога</h2>
      <div class="bar">
        <span style="width:${pos}%;background:var(--good)"></span>
        <span style="width:${neu}%;background:#b9b5d4"></span>
        <span style="width:${neg}%;background:var(--bad)"></span>
      </div>
      <div class="legend">
        <span><span class="dot" style="background:var(--good)"></span>Позитив ${pos}%</span>
        <span><span class="dot" style="background:#b9b5d4"></span>Нейтрально ${neu}%</span>
        <span><span class="dot" style="background:var(--bad)"></span>Негатив ${neg}%</span>
      </div>

      ${compliance ? `<h2 class="sec">Этапы скрипта</h2><div style="display:flex;flex-direction:column;gap:8px">${compliance}</div>` : ""}
      ${fillers ? `<h2 class="sec">Слова-паразиты</h2><div>${fillers}</div>` : ""}
      ${a.strengths?.length ? `<h2 class="sec">Сильные стороны</h2>${list(a.strengths, "💪")}` : ""}
      ${a.weaknesses?.length ? `<h2 class="sec">Слабые стороны</h2>${list(a.weaknesses, "⚠️")}` : ""}
      ${fixes ? `<h2 class="sec">Ошибки и как исправить</h2>${fixes}` : ""}
      ${a.recommendations?.length ? `<h2 class="sec">Рекомендации</h2>${list(a.recommendations, "🎯")}` : ""}
      ${chat ? `<h2 class="sec">Диалог</h2><div class="chat">${chat}</div>` : ""}
    `;
  }

  async function showAnalysis(id) {
    const body = openModal('<p class="muted">Загружаю разбор…</p>');
    try {
      const d = await Onvy.api(`/analytics/analyses/${id}`);
      body.innerHTML = analysisHtml(d);
    } catch (e) { body.innerHTML = `<p class="muted">Ошибка: ${esc(e.message)}</p>`; }
  }

  function analysisListItem(a) {
    const kpi = a.kpi_score ?? 0;
    const sold = a.is_sold ? '<span class="pill on">💰 продажа</span>' : '<span class="pill off">без продажи</span>';
    return `<div class="item-click" onclick="OnvyUI.showAnalysis(${a.id})">
      <div class="spread"><b>Разбор #${a.id}</b>
        <span><span class="pill" style="background:${kpi >= 70 ? "var(--good-soft)" : kpi >= 40 ? "var(--warn-soft)" : "var(--bad-soft)"};color:${kpi >= 70 ? "var(--good)" : kpi >= 40 ? "var(--warn)" : "var(--bad)"}">KPI ${kpi}</span> ${sold}</span>
      </div>
      <div class="muted small" style="margin-top:4px">${esc(a.summary || "—")}</div>
    </div>`;
  }

  // --- Плеер курса ---
  function openCourse(course, employeeId) {
    const steps = course.steps || [];
    let idx = 0;
    const body = openModal("<div id='cp'></div>");
    const box = body.querySelector("#cp");

    async function saveProgress(pct) {
      if (!employeeId) return;
      try {
        await Onvy.api("/courses/progress", {
          method: "POST",
          body: JSON.stringify({ employee_id: employeeId, course_id: course.id, progress: pct }),
        });
      } catch { /* прогресс не критичен для показа */ }
    }

    function render() {
      const dots = steps.map((_, i) => `<span class="${i <= idx ? "done" : ""}"></span>`).join("");
      if (idx >= steps.length) {
        box.innerHTML = `<div style="text-align:center;padding:20px 4px">
          <div style="font-size:44px">🏆</div><h3>Курс пройден!</h3>
          <p class="muted">+25 очков в твой кабинет</p></div>`;
        saveProgress(100);
        return;
      }
      const st = steps[idx];
      let inner = "";
      if (st.type === "quiz" && st.question) {
        const q = st.question;
        inner = `<p><b>${esc(q.text)}</b></p>` + (q.options || []).map((o, i) =>
          `<button class="quiz-opt" data-i="${i}">${esc(o)}</button>`).join("");
      } else {
        inner = `<p style="white-space:pre-wrap">${esc(st.content || "")}</p>
          <button class="small" id="cnext">Дальше →</button>`;
      }
      box.innerHTML = `<div class="muted small">${esc(course.title)}</div>
        <div class="stepdots">${dots}</div><h3 style="margin:6px 0 10px">${esc(st.title || "")}</h3>${inner}`;

      const next = () => { idx += 1; saveProgress(Math.round((idx / steps.length) * 100)); render(); };
      const nBtn = box.querySelector("#cnext");
      if (nBtn) nBtn.onclick = next;
      box.querySelectorAll(".quiz-opt").forEach((b) => {
        b.onclick = () => {
          const ok = Number(b.dataset.i) === (st.question.correctOption ?? 0);
          b.classList.add(ok ? "right" : "wrong");
          if (ok) setTimeout(next, 650);
        };
      });
    }
    render();
  }

  function courseCard(c, employeeId) {
    const pct = c.progress || 0;
    return `<div class="item-click" data-course="${c.id}">
      <div class="spread"><b>${esc(c.title)}</b><span class="pill">${esc(c.category)}</span></div>
      <div class="muted small" style="margin:4px 0 8px">${esc(c.description)}</div>
      <div class="progress"><span style="width:${pct}%"></span></div>
      <div class="muted small" style="margin-top:4px">${pct}% · ${(c.steps || []).length} шагов</div>
    </div>`;
  }

  return { esc, openModal, analysisHtml, showAnalysis, analysisListItem, openCourse, courseCard };
})();
