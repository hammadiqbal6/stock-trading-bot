(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = { snapshot: null, busy: false };

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 4200);
  }

  function setLoading(on) {
    state.busy = on;
    $("#loading").classList.toggle("hidden", !on);
    $$("#btn-run, #btn-run-2, #btn-validate").forEach((b) => {
      b.disabled = on;
    });
  }

  function money(n) {
    if (n === undefined || n === null || Number.isNaN(n)) return "—";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2,
    }).format(n);
  }

  function pct(n) {
    if (n === undefined || n === null || Number.isNaN(n)) return "—";
    const v = (n * 100).toFixed(2) + "%";
    return v;
  }

  function showView(name) {
    $$(".view").forEach((v) => v.classList.remove("active"));
    $$(".nav-link").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
    const view = $(`#view-${name}`);
    if (view) view.classList.add("active");
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { Accept: "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const g = data.guidance || data.detail?.guidance || data.message || res.statusText;
      throw new Error(g);
    }
    return data;
  }

  function renderMarket(snap) {
    const m = snap.market || {};
    const pill = $("#market-pill");
    if (m.is_open) {
      pill.dataset.state = "open";
      pill.textContent = "Market open";
    } else {
      pill.dataset.state = "closed";
      pill.textContent = "Market closed";
    }
    $("#mode-pill").textContent = snap.mode || "paper";
  }

  function renderOverview(snap) {
    const acct = snap.account || {};
    const risk = snap.risk || {};
    $("#equity-hero").textContent = money(acct.equity);
    $("#guidance-hero").textContent = snap.guidance || risk.guidance || "—";
    $("#metric-cash").textContent = money(acct.cash);
    $("#metric-bp").textContent = money(acct.buying_power);
    const daily = risk.daily_pnl_pct;
    const dd = risk.drawdown_pct;
    const dailyEl = $("#metric-daily");
    const ddEl = $("#metric-dd");
    dailyEl.textContent = pct(daily);
    ddEl.textContent = pct(dd);
    dailyEl.className = "metric-value " + (daily < 0 ? "neg" : daily > 0 ? "pos" : "");
    ddEl.className = "metric-value " + (dd > 0.05 ? "neg" : "");

    const tbody = $("#positions-table tbody");
    tbody.innerHTML = "";
    const positions = snap.positions || [];
    $("#positions-empty").classList.toggle("hidden", positions.length > 0);
    $("#positions-table").classList.toggle("hidden", positions.length === 0);
    for (const p of positions) {
      const tr = document.createElement("tr");
      const upl = p.unrealized_pl || 0;
      tr.innerHTML = `
        <td>${p.symbol}</td>
        <td class="mono">${Number(p.qty).toFixed(4)}</td>
        <td class="mono">${money(p.avg_entry_price)}</td>
        <td class="mono">${money(p.current_price)}</td>
        <td class="mono">${money(p.market_value)}</td>
        <td class="mono ${upl < 0 ? "neg" : "pos"}">${money(upl)}</td>`;
      tbody.appendChild(tr);
    }
  }

  function renderSignals(snap) {
    const tbody = $("#signals-table tbody");
    tbody.innerHTML = "";
    const targets = snap.targets || [];
    $("#signals-empty").classList.toggle("hidden", targets.length > 0);
    $("#signals-table").classList.toggle("hidden", targets.length === 0);
    for (const t of targets) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${t.symbol}</td>
        <td class="mono">${(t.weight * 100).toFixed(2)}%</td>
        <td class="mono">${t.sentiment_score == null ? "—" : t.sentiment_score.toFixed(2)}</td>
        <td class="${t.blocked ? "blocked" : ""}">${t.blocked ? "yes" : "no"}</td>
        <td>${t.blocked ? t.block_reason || t.reason : t.reason}</td>`;
      tbody.appendChild(tr);
    }
  }

  function renderNews(snap) {
    const box = $("#news-list");
    box.innerHTML = "";
    const sent = snap.sentiment || {};
    const keys = Object.keys(sent);
    $("#news-empty").classList.toggle("hidden", keys.length > 0);
    for (const sym of keys) {
      const s = sent[sym];
      const item = document.createElement("article");
      item.className = "news-item";
      const scoreClass = s.score < -0.2 ? "neg" : s.score > 0.2 ? "pos" : "";
      item.innerHTML = `
        <h3>${sym}</h3>
        <div class="news-meta ${scoreClass}">score ${s.score.toFixed(3)} · ${s.method} · ${s.n_articles} articles</div>
        <p>${s.guidance || ""}</p>
        <ul>${(s.headlines || []).map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>`;
      box.appendChild(item);
    }
  }

  function renderRisk(snap) {
    const risk = snap.risk || {};
    const limits = risk.limits || {};
    const rows = [
      ["Kill switch", risk.kill_switch ? `ON — ${risk.kill_reason}` : "off"],
      ["Daily P&L", pct(risk.daily_pnl_pct)],
      ["Drawdown", pct(risk.drawdown_pct)],
      ["Day trades today", risk.day_trades_today ?? "—"],
      ["Max position", pct(limits.max_position_pct)],
      ["Daily loss cap", pct(limits.daily_loss_cap_pct)],
      ["Max drawdown", pct(limits.max_drawdown_pct)],
      ["PDT aware", String(limits.pdt_aware)],
      ["Fractional shares", String(limits.fractional_shares)],
      ["Guidance", risk.guidance || "—"],
    ];
    $("#risk-kv").innerHTML = rows
      .map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(String(v))}</dd>`)
      .join("");
  }

  function renderLogs(snap) {
    const logs = snap.logs || [];
    $("#logs-block").textContent = logs.length ? logs.join("\n") : "No logs in last cycle.";
  }

  function renderSetup(setup) {
    const steps = $("#setup-steps");
    steps.innerHTML = "";
    const order = ["alpaca", "finnhub", "llm", "gdelt", "finbert", "live_gate"];
    order.forEach((key, i) => {
      const item = setup[key];
      if (!item) return;
      const li = document.createElement("li");
      li.className = "setup-step";
      let badgeClass = "opt";
      let badgeText = "opt";
      if (item.required && item.configured) {
        badgeClass = "ok";
        badgeText = "ok";
      } else if (item.required && !item.configured) {
        badgeClass = "bad";
        badgeText = "!";
      } else if (item.configured) {
        badgeClass = "ok";
        badgeText = "ok";
      }
      const title = key.replaceAll("_", " ");
      li.innerHTML = `
        <div class="step-badge ${badgeClass}">${badgeText}</div>
        <div>
          <h3>${title}</h3>
          <p>${escapeHtml(item.guidance || "")}</p>
        </div>`;
      steps.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return s
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderAll(snap) {
    state.snapshot = snap;
    renderMarket(snap);
    renderOverview(snap);
    renderSignals(snap);
    renderNews(snap);
    renderRisk(snap);
    renderLogs(snap);
    if (snap.setup) renderSetup(snap.setup);
  }

  async function refreshStatus() {
    try {
      const snap = await api("/api/status");
      renderAll(snap);
    } catch (err) {
      toast(err.message || "Status failed");
      $("#guidance-hero").textContent = err.message;
    }
  }

  async function runCycle() {
    setLoading(true);
    try {
      const snap = await api("/api/run", { method: "POST" });
      renderAll(snap);
      toast(snap.ok ? "Cycle complete" : "Cycle finished with issues — see guidance");
    } catch (err) {
      toast(err.message || "Run failed");
    } finally {
      setLoading(false);
    }
  }

  async function loadValidation() {
    setLoading(true);
    try {
      const data = await api("/api/validation/latest");
      if (!data.ok) {
        $("#validation-guidance").textContent = data.guidance;
        $("#validation-json").textContent = data.guidance;
        toast(data.guidance);
        return;
      }
      $("#validation-guidance").textContent = data.report.guidance || data.report.honest_disclaimer;
      $("#validation-json").textContent = JSON.stringify(data.report, null, 2);
    } catch (err) {
      toast(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function runValidation() {
    setLoading(true);
    toast("Validation started — may take a minute (yfinance download)…");
    try {
      const data = await api("/api/validation/run", { method: "POST" });
      $("#validation-guidance").textContent = data.guidance || data.report?.guidance || "";
      $("#validation-json").textContent = JSON.stringify(data.report, null, 2);
      toast("Validation report ready");
      showView("validation");
    } catch (err) {
      toast(err.message || "Validation failed — check network / keys guidance");
      $("#validation-guidance").textContent = err.message;
    } finally {
      setLoading(false);
    }
  }

  function bind() {
    $$(".nav-link").forEach((btn) =>
      btn.addEventListener("click", () => showView(btn.dataset.view))
    );
    $$("[data-view-jump]").forEach((btn) =>
      btn.addEventListener("click", () => showView(btn.dataset.viewJump))
    );
    $("#btn-run").addEventListener("click", runCycle);
    $("#btn-run-2").addEventListener("click", runCycle);
    $("#btn-load-validation").addEventListener("click", loadValidation);
    $("#btn-validate").addEventListener("click", runValidation);
    $("#btn-reload").addEventListener("click", async () => {
      try {
        await api("/api/reload-settings", { method: "POST" });
        const setup = await api("/api/setup");
        renderSetup(setup);
        toast("Settings reloaded");
      } catch (err) {
        toast(err.message);
      }
    });
    $("#btn-reset-kill").addEventListener("click", async () => {
      const confirm = window.prompt("Type RESET_KILL_SWITCH to confirm");
      if (!confirm) return;
      try {
        await api(`/api/risk/reset-kill-switch?confirm=${encodeURIComponent(confirm)}`, {
          method: "POST",
        });
        toast("Kill switch reset");
        refreshStatus();
      } catch (err) {
        toast(err.message || "Reset failed");
      }
    });
  }

  bind();
  refreshStatus();
  setInterval(refreshStatus, 30000);
})();
