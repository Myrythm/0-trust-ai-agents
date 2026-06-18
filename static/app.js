// Polls /api/audit every 3s when on the audit page; updates the table
// and the chain-valid banner. No framework; no dependencies.
(function () {
  const REFRESH_MS = 3000;

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderEventRow(e) {
    const ts = escapeHtml(e.ts);
    const agent = escapeHtml(e.agent_id);
    const action = escapeHtml(e.action);
    const decision = escapeHtml(e.decision);
    const reason = escapeHtml(e.reason || "");
    const rid = escapeHtml((e.request_id || "").slice(0, 12) + "\u2026");
    const hash = escapeHtml((e.this_hash || "").slice(0, 12) + "\u2026");
    return (
      "<tr>" +
      '<td class="ts">' + ts + "</td>" +
      "<td>" + agent + "</td>" +
      "<td><code>" + action + "</code></td>" +
      '<td><span class="badge badge-' + decision + '">' + decision + "</span></td>" +
      '<td class="reason">' + reason + "</td>" +
      '<td class="rid"><code>' + rid + "</code></td>" +
      '<td class="hash"><code>' + hash + "</code></td>" +
      "</tr>"
    );
  }

  function start() {
    const tableBody = document.querySelector(".audit-table tbody");
    const banner = document.querySelector(".banner");
    if (!tableBody || !banner) return;

    function refresh() {
      fetch("/api/audit", { headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (body) {
          const events = (body.events || []).slice().reverse();
          if (events.length === 0) {
            tableBody.innerHTML = "";
          } else {
            tableBody.innerHTML = events.map(renderEventRow).join("");
          }
          if (body.chain_valid) {
            banner.className = "banner banner-ok";
            banner.textContent = "Chain valid \u00b7 " + events.length + " event(s)";
          } else {
            banner.className = "banner banner-error";
            banner.textContent = "CHAIN TAMPERED \u2014 investigate immediately";
          }
        })
        .catch(function () { /* ignore transient errors */ });
    }

    refresh();
    setInterval(refresh, REFRESH_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
