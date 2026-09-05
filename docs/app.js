const REFRESH_MS = 5 * 60 * 1000; // re-check data.json every 5 min

function fmt(n, digits = 1) {
  return (n === null || n === undefined) ? "-" : Number(n).toFixed(digits);
}

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function injuryBadge(status) {
  if (!status || status === "ACTIVE" || status === "NORMAL") return "";
  return `<span class="badge injury">${esc(status)}</span>`;
}

function renderMatchup(data) {
  const m = data.matchup;
  document.getElementById("matchup").innerHTML = `
    <div class="card">
      <div class="matchup-row">
        <div>
          <div class="score mine">${fmt(m.my_score, 1)}</div>
          <div class="proj">${data.team_name} &middot; proj ${fmt(m.my_projected, 1)}</div>
        </div>
        <div style="text-align:right">
          <div class="score theirs">${fmt(m.opp_score, 1)}</div>
          <div class="proj">${esc(m.opponent_name || "opponent")} &middot; proj ${fmt(m.opp_projected, 1)}</div>
        </div>
      </div>
    </div>
  `;
}

function playerRow(p, { bench = false } = {}) {
  if (!p) {
    return `<tr class="no-player"><td colspan="4">No eligible player found</td></tr>`;
  }
  return `
    <tr class="${bench ? "bench-row" : ""}">
      <td>${esc(p.name)}</td>
      <td class="pos-${esc(p.pos)}">${esc(p.pos)}</td>
      <td class="num">${fmt(p.proj_week_pts, 1)}</td>
      <td>${injuryBadge(p.injury_status)}</td>
    </tr>
  `;
}

function renderLineup(data) {
  const l = data.lineup;
  const starterRows = l.recommended_starters.map((s) => `
    <tr>
      <td><strong>${esc(s.slot)}</strong></td>
      <td>${s.player ? esc(s.player.name) : '<span style="color:#a00">NONE ELIGIBLE</span>'}</td>
      <td class="pos-${s.player ? esc(s.player.pos) : ""}">${s.player ? esc(s.player.pos) : ""}</td>
      <td class="num">${s.player ? fmt(s.player.proj_week_pts, 1) : "-"}</td>
      <td>${s.player ? injuryBadge(s.player.injury_status) : ""}</td>
    </tr>
  `).join("");

  const benchRows = l.bench.map((p) => `
    <tr class="bench-row">
      <td colspan="2">${esc(p.name)}</td>
      <td class="pos-${esc(p.pos)}">${esc(p.pos)}</td>
      <td class="num">${fmt(p.proj_week_pts, 1)}</td>
      <td>${injuryBadge(p.injury_status)}</td>
    </tr>
  `).join("");

  const reasoning = l.reasoning.length
    ? `<ul class="reasoning">${l.reasoning.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`
    : `<p class="proj">Your current lineup already matches the recommendation -- no changes needed.</p>`;

  document.getElementById("lineup").innerHTML = `
    <div class="card">
      <p class="proj">Projected total: <strong>${fmt(l.projected_total, 2)}</strong> pts</p>
      <table>
        <thead><tr><th>Slot</th><th>Player</th><th>Pos</th><th class="num">Proj</th><th></th></tr></thead>
        <tbody>${starterRows}</tbody>
      </table>
      ${reasoning}
      <h3 style="font-size:.9rem;margin:1rem 0 .3rem;">Bench</h3>
      <table>
        <tbody>${benchRows}</tbody>
      </table>
    </div>
  `;
}

function renderWaivers(data) {
  const rows = data.waiver_targets.map((t) => `
    <tr>
      <td>${esc(t.name)}</td>
      <td class="pos-${esc(t.pos)}">${esc(t.pos)}</td>
      <td class="num">${fmt(t.proj_value, 2)}</td>
      <td class="num">${t.percent_owned != null ? fmt(t.percent_owned, 0) + "%" : "-"}</td>
      <td class="num">${t.percent_started != null ? fmt(t.percent_started, 0) + "%" : "-"}</td>
      <td>${t.recent_activity_note ? esc(t.recent_activity_note) : ""}</td>
    </tr>
  `).join("");

  document.getElementById("waivers").innerHTML = `
    <div class="card">
      <table>
        <thead>
          <tr><th>Name</th><th>Pos</th><th class="num">Value</th><th class="num">Own%</th><th class="num">Start%</th><th>Recent activity</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function render(data) {
  document.getElementById("week-label").textContent = `Week ${data.week}`;
  document.getElementById("updated").textContent =
    "Last updated: " + new Date(data.generated_at).toLocaleString();
  renderMatchup(data);
  renderLineup(data);
  renderWaivers(data);
}

async function load() {
  try {
    const res = await fetch("data.json?ts=" + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    render(await res.json());
  } catch (err) {
    document.getElementById("matchup").innerHTML =
      `<div class="error">Couldn't load data.json yet (${esc(err.message)}). ` +
      `If this is a fresh deploy, the first GitHub Actions run hasn't completed.</div>`;
  }
}

load();
setInterval(load, REFRESH_MS);
