// Chart.js wiring for the loan detail, strategy comparison, and net-worth pages.
// Each canvas reads its data from data-* attributes set by the template, so
// this file is decoupled from any single page's structure.
(function () {
  "use strict";
  if (typeof Chart === "undefined") return;

  function parse(el, key) {
    try {
      return JSON.parse(el.getAttribute(key) || "[]");
    } catch (e) {
      return [];
    }
  }

  // Loan detail: predicted vs logged balance.
  var bal = document.getElementById("balance-chart");
  if (bal) {
    var predicted = parse(bal, "data-predicted");
    var history = parse(bal, "data-history");
    new Chart(bal, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Predicted",
            data: predicted.map(function (p) { return { x: p[0], y: parseFloat(p[1]) }; }),
            borderColor: "#38bdf8",
            tension: 0.2,
          },
          {
            label: "Logged",
            data: history.map(function (p) { return { x: p[0], y: parseFloat(p[1]) }; }),
            borderColor: "#facc15",
            tension: 0.1,
          },
        ],
      },
      options: {
        responsive: true,
        scales: { x: { type: "category" } },
      },
    });
  }

  // Strategy comparison: combined balance over time.
  var strat = document.getElementById("strategy-chart");
  if (strat) {
    var snowball = parse(strat, "data-snowball");
    var avalanche = parse(strat, "data-avalanche");
    new Chart(strat, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Snowball",
            data: snowball.map(function (p) { return { x: p[0], y: parseFloat(p[1]) }; }),
            borderColor: "#38bdf8",
          },
          {
            label: "Avalanche",
            data: avalanche.map(function (p) { return { x: p[0], y: parseFloat(p[1]) }; }),
            borderColor: "#4ade80",
          },
        ],
      },
      options: { responsive: true, scales: { x: { type: "category" } } },
    });
  }

  // Net worth trend.
  var nw = document.getElementById("networth-chart");
  if (nw) {
    var trend = parse(nw, "data-trend");
    new Chart(nw, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Net worth",
            data: trend.map(function (p) { return { x: p[0], y: parseFloat(p[1]) }; }),
            borderColor: "#38bdf8",
            tension: 0.2,
          },
        ],
      },
      options: { responsive: true, scales: { x: { type: "category" } } },
    });
  }
})();
