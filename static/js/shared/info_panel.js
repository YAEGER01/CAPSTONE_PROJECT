(function () {
  var fab = document.getElementById("infoFab");
  var panel = document.getElementById("infoPanel");
  var overlay = document.getElementById("infoPanelOverlay");
  var contentContainer = document.getElementById("infoPanelContent");
  var loaded = false;

  function openPanel() {
    if (!loaded && contentContainer) {
      contentContainer.innerHTML = '<div style="padding:24px;text-align:center;color:#999;"><i class="fa-solid fa-spinner fa-spin"></i> Loading...</div>';
      fetch("/hx/info/")
        .then(function (r) { return r.text(); })
        .then(function (html) { contentContainer.innerHTML = html; })
        ["catch"](function () {
          contentContainer.innerHTML =
            '<div class="info-panel-body"><p style="padding:20px;color:#999;">Failed to load help content.</p></div>';
        });
      loaded = true;
    }
    panel.classList.add("open");
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closePanel() {
    panel.classList.remove("open");
    overlay.classList.remove("open");
    document.body.style.overflow = "";
  }

  window.toggleInfoPanel = function () {
    if (panel.classList.contains("open")) {
      closePanel();
    } else {
      openPanel();
    }
  };

  if (overlay) {
    overlay.addEventListener("click", closePanel);
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && panel && panel.classList.contains("open")) {
      closePanel();
    }
  });

  window.toggleInfoTopic = function (headerEl) {
    var topic = headerEl.closest(".info-topic");
    if (!topic) return;
    topic.classList.toggle("open");
  };
})();
