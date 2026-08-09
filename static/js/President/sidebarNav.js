function setupCollapsibleSidebar() {
  const sidebar = document.getElementById("appSidebar");
  const collapseBtn = document.getElementById("collapseBtn");
  const chevronIcon = document.getElementById("chevronLeftIcon");

  collapseBtn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
    if (sidebar.classList.contains("collapsed")) {
      chevronIcon.innerHTML = `<polyline points="9 18 15 12 9 6"></polyline>`;
      collapseBtn.setAttribute("title", "Expand Sidebar Menu");
    } else {
      chevronIcon.innerHTML = `<polyline points="15 18 9 12 15 6"></polyline>`;
      collapseBtn.setAttribute("title", "Collapse Sidebar Menu");
    }
  });
}

function setupFolders() {
  const activeLink = document.querySelector(".menu-item.active");
  if (activeLink) {
    const parentFolder = activeLink.closest(".nested-folder");
    if (parentFolder) {
      const contents = parentFolder.querySelector(".folder-contents");
      const header = parentFolder.querySelector(".folder-header");
      contents.classList.add("open");
      const chevron = header.querySelector(".chevron-icon");
      if (chevron) chevron.style.transform = "rotate(180deg)";
    }
  }
}

function toggleFolder(folderId, headerElement) {
  const sidebar = document.getElementById("appSidebar");
  if (sidebar.classList.contains("collapsed")) {
    sidebar.classList.remove("collapsed");
    document.getElementById("chevronLeftIcon").innerHTML =
      `<polyline points="15 18 9 12 15 6"></polyline>`;
  }

  const contents = document.getElementById(folderId);
  const isOpen = contents.classList.contains("open");

  document.querySelectorAll(".folder-contents").forEach((el) => {
    el.classList.remove("open");
    const parentHeader = el.parentElement.querySelector(".chevron-icon");
    if (parentHeader) parentHeader.style.transform = "rotate(0deg)";
  });

  if (!isOpen) {
    contents.classList.add("open");
    const chevron = headerElement.querySelector(".chevron-icon");
    if (chevron) chevron.style.transform = "rotate(180deg)";
  }
}

function setupNavigation() {
  const menuItems = document.querySelectorAll(".menu-item");
  menuItems.forEach((item) => {
    item.addEventListener("click", () => {
      const target = item.getAttribute("data-target");
      if (!target) return;

      menuItems.forEach((mi) => mi.classList.remove("active"));
      item.classList.add("active");

      document.querySelectorAll(".dashboard-module").forEach((mod) => {
        mod.classList.remove("active");
        if (mod.id === target) {
          mod.classList.add("active");
        }
      });

      document.getElementById("appSidebar").classList.remove("open-mobile");

      const title = item.querySelector(".menu-text").innerText;
      document.getElementById("currentModuleTitle").innerText = title;
    });
  });

  document
    .getElementById("mobileSidebarToggle")
    .addEventListener("click", () => {
      document.getElementById("appSidebar").classList.add("open-mobile");
    });
}
