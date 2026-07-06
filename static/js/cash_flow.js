(function () {
  "use strict";

  function fmt(num) {
    return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" }).format(num);
  }

  async function init() {
    try {
      var res = await fetch("/api/cash-flow-summary/", { method: "GET", credentials: "same-origin" });
      var data = await res.json();
      if (!data || !data.ok) return;

      var fundsIn = document.getElementById("cf-funds-in");
      var fundsOut = document.getElementById("cf-funds-out");
      var pending = document.getElementById("cf-pending-contributions");
      if (fundsIn) fundsIn.innerText = fmt(data.funds_in);
      if (fundsOut) fundsOut.innerText = fmt(data.funds_out);
      if (pending) pending.innerText = fmt(data.pending_contributions);

      var canvas = document.getElementById("cf-chart");
      if (!canvas || typeof Chart === "undefined") return;
      if (canvas.__chart) canvas.__chart.destroy();
      canvas.__chart = new Chart(canvas.getContext("2d"), {
        type: "bar",
        data: {
          labels: ["Funds In", "Releases Out", "Pending Contributions"],
          datasets: [{
            label: "Amount (₱)",
            data: [data.funds_in, data.funds_out, data.pending_contributions],
            backgroundColor: ["rgba(27,94,32,0.8)", "rgba(229,57,53,0.8)", "rgba(245,124,0,0.8)"],
            borderColor: ["#1b5e20", "#e53935", "#f57c00"],
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return "₱" + Number(ctx.raw).toLocaleString("en-PH", { minimumFractionDigits: 2 });
                },
              },
            },
          },
          scales: {
            x: { grid: { display: false } },
            y: {
              beginAtZero: true,
              grid: { color: "rgba(0,0,0,0.06)" },
              ticks: {
                callback: function (v) {
                  return "₱" + (v >= 1000 ? (v / 1000).toFixed(0) + "k" : v);
                },
              },
            },
          },
        },
      });
    } catch (e) {
      console.error("Cash flow init failed:", e);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
