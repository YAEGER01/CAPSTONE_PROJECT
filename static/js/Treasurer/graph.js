(function () {
  "use strict";

  console.log("[graph.js] loaded, Chart available:", typeof Chart !== "undefined");

  const POSTS_URL = "/api/treasurer/approved-aid-posts/";
  const HISTORY_URL = "/api/treasurer/aid-post-history/";

  let chartInstance = null;
  let postsData = [];
  let historyData = [];

  async function fetchJSON(url) {
    try {
      var resp = await fetch(url, { method: "GET", credentials: "same-origin" });
      var data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || "Fetch failed");
      return data;
    } catch (e) {
      return null;
    }
  }

  function formatMoney(num) {
    return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" }).format(num);
  }

  async function loadChartData() {
    var activeData = await fetchJSON(POSTS_URL);
    var historyDataResp = await fetchJSON(HISTORY_URL);

    postsData = (activeData && activeData.posts) || [];
    historyData = (historyDataResp && historyDataResp.posts) || [];
  }

  function buildChart() {
    console.log("[graph.js] buildChart() called, postsData:", postsData.length);
    var canvas = document.getElementById("aidTrackingChart");
    if (!canvas) {
      console.warn("[graph.js] canvas #aidTrackingChart not found");
      return;
    }

    var ctx = canvas.getContext("2d");

    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }

    var labels = [];
    var expectedData = [];
    var collectedData = [];
    var colors = [];

    postsData.forEach(function (p) {
      var label = p.member_name || "Post #" + p.post_id;
      if (label.length > 18) label = label.substring(0, 16) + "...";
      labels.push(label);
      expectedData.push(parseFloat(p.total_expected || 0));
      collectedData.push(parseFloat(p.total_collected || 0));
      colors.push(p.aid_type === "medical_aid" ? "#2dd4bf" : "#a5b4fc");
    });

    if (labels.length === 0) {
      canvas.style.display = "none";
      var container = document.getElementById("aidChartContainer");
      if (container) container.style.height = "auto";
      var noDataEl = document.getElementById("aidChartNoData");
      if (noDataEl) noDataEl.style.display = "block";
      var summaryEl = document.getElementById("aidChartSummary");
      if (summaryEl) summaryEl.style.display = "none";
      return;
    }

    canvas.style.display = "block";
    var container = document.getElementById("aidChartContainer");
    if (container) container.style.height = "280px";
    var noDataEl = document.getElementById("aidChartNoData");
    if (noDataEl) noDataEl.style.display = "none";
    var summaryEl = document.getElementById("aidChartSummary");
    if (summaryEl) summaryEl.style.display = "block";

    try {
      chartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Expected",
            data: expectedData,
            backgroundColor: "rgba(27, 94, 32, 0.7)",
            borderColor: "#1b5e20",
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: "Collected",
            data: collectedData,
            backgroundColor: "rgba(251, 192, 45, 0.8)",
            borderColor: "#fbc02d",
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
            labels: {
              font: { family: "Poppins, sans-serif", size: 11 },
              boxWidth: 14,
              padding: 14,
            },
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return context.dataset.label + ": " + formatMoney(context.raw);
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              font: { family: "Poppins, sans-serif", size: 10 },
              maxRotation: 30,
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(0,0,0,0.06)" },
            ticks: {
              font: { family: "Poppins, sans-serif", size: 10 },
              callback: function (value) {
                if (value >= 1000) return "₱" + (value / 1000).toFixed(0) + "k";
                return "₱" + value;
              },
            },
          },
        },
      },
    });
    } catch (e) {
      console.error("[graph.js] Chart creation failed:", e);
    }

    updateSummary();
  }

  function updateSummary() {
    var el = document.getElementById("aidChartSummary");
    if (!el) return;

    var totalExpected = 0;
    var totalCollected = 0;
    var activeCount = postsData.length;
    var completedCount = 0;

    postsData.forEach(function (p) {
      totalExpected += parseFloat(p.total_expected || 0);
      totalCollected += parseFloat(p.total_collected || 0);
      if (p.collection_rate >= 100) completedCount++;
    });

    var rate = totalExpected > 0 ? Math.round((totalCollected / totalExpected) * 100) : 0;

    el.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:14px;">' +
      '<div style="background:#f6fbf6;border-radius:10px;padding:10px;text-align:center;">' +
      '<div style="font-size:0.7rem;color:#757575;">Active Posts</div>' +
      '<div style="font-weight:700;font-size:1.1rem;color:#263238;">' + activeCount + "</div></div>" +
      '<div style="background:#f6fbf6;border-radius:10px;padding:10px;text-align:center;">' +
      '<div style="font-size:0.7rem;color:#757575;">Total Expected</div>' +
      '<div style="font-weight:700;font-size:1.1rem;color:#1b5e20;">' + formatMoney(totalExpected) + "</div></div>" +
      '<div style="background:#f6fbf6;border-radius:10px;padding:10px;text-align:center;">' +
      '<div style="font-size:0.7rem;color:#757575;">Total Collected</div>' +
      '<div style="font-weight:700;font-size:1.1rem;color:#fbc02d;">' + formatMoney(totalCollected) + "</div></div>" +
      '<div style="background:#f6fbf6;border-radius:10px;padding:10px;text-align:center;">' +
      '<div style="font-size:0.7rem;color:#757575;">Collection Rate</div>' +
      '<div style="font-weight:700;font-size:1.1rem;color:' + (rate >= 100 ? "#1b5e20" : rate >= 50 ? "#fbc02d" : "#e53935") + ';">' + rate + "%</div></div>" +
      '<div style="background:#f6fbf6;border-radius:10px;padding:10px;text-align:center;">' +
      '<div style="font-size:0.7rem;color:#757575;">Fully Collected</div>' +
      '<div style="font-weight:700;font-size:1.1rem;color:#1b5e20;">' + completedCount + "/" + activeCount + "</div></div>" +
      "</div>";
  }

  function navigateToAidTracking() {
    if (typeof setActiveModule === "function") {
      setActiveModule("treasurer-aid-tracking-posts");
    }
  }

  async function init() {
    console.log("[graph.js] init() called");
    try {
      await loadChartData();
      buildChart();
    } catch (e) {
      console.error("[graph.js] init error:", e);
    }
  }

  window.AidTrackingGraph = {
    init: init,
    refresh: function () {
      loadChartData().then(buildChart);
    },
    navigateToAidTracking: navigateToAidTracking,
  };

  document.addEventListener("DOMContentLoaded", function () {
    console.log("[graph.js] DOMContentLoaded");
    try {
      var tab = document.getElementById("dashboard-overview");
      console.log("[graph.js] dashboard-overview tab:", tab, tab ? "active=" + tab.classList.contains("active") : "null");
      if (tab && tab.classList.contains("active")) {
        init();
      }
      var observer = new MutationObserver(function () {
        if (tab && tab.classList.contains("active")) {
          if (!postsData || postsData.length === 0) {
            init();
          } else {
            buildChart();
          }
        }
      });
      if (tab) {
        observer.observe(tab, { attributes: true, attributeFilter: ["class"] });
      }

      var seeDetailsBtn = document.getElementById("seeFullAidDetails");
      if (seeDetailsBtn) {
        seeDetailsBtn.addEventListener("click", function (e) {
          e.preventDefault();
          if (window.AidTrackingGraph && typeof window.AidTrackingGraph.navigateToAidTracking === "function") {
            window.AidTrackingGraph.navigateToAidTracking();
          }
        });
      }
    } catch (e) {
      console.error("[graph.js] DOMContentLoaded error:", e);
    }
  });
})();