// Chart.js wiring for the loan detail, strategy comparison, and net-worth pages.
// Each canvas reads its data from data-* attributes set by the template, so
// this file is decoupled from any single page's structure.
(function () {
  "use strict";
  if (typeof Chart === "undefined") return;

  var currencyTick = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  var currencyExact = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });

  function parse(el, key) {
    try {
      return JSON.parse(el.getAttribute(key) || "[]");
    } catch (e) {
      return [];
    }
  }

  // Custom plugin: draw inline labels at the right end of each visible
  // dataset. Cheaper and stickier than relying on the legend.
  var endpointLabels = {
    id: "endpointLabels",
    afterDatasetsDraw: function (chart) {
      var ctx = chart.ctx;
      ctx.save();
      ctx.font = "12px -apple-system, BlinkMacSystemFont, sans-serif";
      ctx.textBaseline = "middle";
      chart.data.datasets.forEach(function (ds, idx) {
        if (ds.label === undefined || ds.endpointLabel === false) return;
        var meta = chart.getDatasetMeta(idx);
        if (!meta || !meta.data || meta.data.length === 0) return;
        var last = meta.data[meta.data.length - 1];
        if (!last) return;
        ctx.fillStyle = ds.borderColor || "#e2e8f0";
        ctx.fillText(ds.label, last.x + 6, last.y);
      });
      ctx.restore();
    },
  };

  // ---------- Loan detail balance chart ----------
  var bal = document.getElementById("balance-chart");
  if (bal) {
    var predictedRaw = parse(bal, "data-predicted");
    var historyRaw = parse(bal, "data-history");

    // Sort predicted by date (already chronological from the server, but
    // guard against a future change).
    predictedRaw.sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    historyRaw.sort(function (a, b) { return a.date < b.date ? -1 : 1; });

    var twelveMonthsAgo = new Date();
    twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 12);
    var cutoffIso = twelveMonthsAgo.toISOString().slice(0, 10);

    var showFull = false;

    function buildChart() {
      var predicted = predictedRaw.filter(function (p) {
        return showFull || p.date >= cutoffIso;
      });
      var history = historyRaw.filter(function (p) {
        return showFull || p.date >= cutoffIso;
      });

      var predictedPoints = predicted.map(function (p) {
        return { x: p.date, y: parseFloat(p.balance) };
      });
      var historyPoints = history.map(function (p) {
        return { x: p.date, y: parseFloat(p.balance) };
      });

      // Confidence bands: predicted ± yellow tolerance (inner) and
      // ± red tolerance (outer). Each band is a pair of line datasets
      // with fill between them.
      var yellowUpper = predicted.map(function (p) {
        return { x: p.date, y: parseFloat(p.balance) + parseFloat(p.yellow) };
      });
      var yellowLower = predicted.map(function (p) {
        return { x: p.date, y: parseFloat(p.balance) - parseFloat(p.yellow) };
      });
      var redUpper = predicted.map(function (p) {
        return { x: p.date, y: parseFloat(p.balance) + parseFloat(p.red) };
      });
      var redLower = predicted.map(function (p) {
        return { x: p.date, y: parseFloat(p.balance) - parseFloat(p.red) };
      });

      var datasets = [
        // Red band (outer): drawn first so yellow + lines render on top.
        {
          label: "_redUpper",
          data: redUpper,
          borderWidth: 0,
          pointRadius: 0,
          backgroundColor: "rgba(248, 113, 113, 0.10)",
          fill: "+1",
          endpointLabel: false,
        },
        {
          label: "_redLower",
          data: redLower,
          borderWidth: 0,
          pointRadius: 0,
          fill: false,
          endpointLabel: false,
        },
        // Yellow band (inner).
        {
          label: "_yellowUpper",
          data: yellowUpper,
          borderWidth: 0,
          pointRadius: 0,
          backgroundColor: "rgba(250, 204, 21, 0.18)",
          fill: "+1",
          endpointLabel: false,
        },
        {
          label: "_yellowLower",
          data: yellowLower,
          borderWidth: 0,
          pointRadius: 0,
          fill: false,
          endpointLabel: false,
        },
        // Predicted line: dashed, lighter weight.
        {
          label: "Predicted",
          data: predictedPoints,
          borderColor: "rgba(56, 189, 248, 0.6)",
          borderWidth: 1.5,
          borderDash: [6, 4],
          pointRadius: 0,
          fill: false,
          tension: 0.2,
        },
        // Logged line: solid, full weight.
        {
          label: "Logged",
          data: historyPoints,
          borderColor: "#facc15",
          backgroundColor: "#facc15",
          borderWidth: 2,
          pointRadius: 4,
          tension: 0.1,
        },
      ];

      if (bal._chart) bal._chart.destroy();
      bal._chart = new Chart(bal, {
        type: "line",
        data: { datasets: datasets },
        plugins: [endpointLabels],
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: {
              display: true,
              labels: {
                filter: function (item) {
                  return !item.text || !item.text.startsWith("_");
                },
              },
            },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  if (ctx.dataset.label && ctx.dataset.label.startsWith("_")) {
                    return null;
                  }
                  return ctx.dataset.label + ": " + currencyExact.format(ctx.parsed.y);
                },
                afterBody: function (items) {
                  // Pull the gap = logged - predicted for the same x, if both present.
                  var predicted = null, logged = null;
                  items.forEach(function (i) {
                    if (i.dataset.label === "Predicted") predicted = i.parsed.y;
                    if (i.dataset.label === "Logged") logged = i.parsed.y;
                  });
                  if (predicted !== null && logged !== null) {
                    var gap = logged - predicted;
                    var sign = gap >= 0 ? "+" : "";
                    return "Gap: " + sign + currencyExact.format(gap);
                  }
                  return "";
                },
              },
            },
          },
          scales: {
            x: { type: "category", offset: false },
            y: {
              ticks: {
                callback: function (value) { return currencyTick.format(value); },
              },
            },
          },
          layout: { padding: { right: 56 } },
        },
      });
    }

    buildChart();
    var toggle = document.getElementById("balance-chart-toggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        showFull = !showFull;
        toggle.textContent = showFull ? "Show last 12 months" : "Show full history";
        buildChart();
      });
    }
  }

  // ---------- Strategy comparison ----------
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
            data: snowball.map(function (p) {
              return { x: p[0], y: parseFloat(p[1]) };
            }),
            borderColor: "#38bdf8",
          },
          {
            label: "Avalanche",
            data: avalanche.map(function (p) {
              return { x: p[0], y: parseFloat(p[1]) };
            }),
            borderColor: "#4ade80",
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          x: { type: "category" },
          y: { ticks: { callback: function (v) { return currencyTick.format(v); } } },
        },
      },
    });
  }

  // ---------- Net worth trend ----------
  var nw = document.getElementById("networth-chart");
  if (nw) {
    var trend = parse(nw, "data-trend");
    new Chart(nw, {
      type: "line",
      data: {
        datasets: [
          {
            label: "Net worth",
            data: trend.map(function (p) {
              return { x: p[0], y: parseFloat(p[1]) };
            }),
            borderColor: "#38bdf8",
            tension: 0.2,
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          x: { type: "category" },
          y: { ticks: { callback: function (v) { return currencyTick.format(v); } } },
        },
      },
    });
  }
})();
