(function () {
  var root = document.documentElement;
  var theme = "dark";
  try {
    if (window.localStorage.getItem("cv-theme") === "light") theme = "light";
  } catch (ignore) {}
  root.dataset.theme = theme;

  // Keep the control hidden until it is ready to work.
  document.addEventListener("DOMContentLoaded", function () {
    var timeline = document.querySelector("#timeline");
    if (timeline) {
      var filterInputs = timeline.querySelectorAll('.filters input[name="timeline-filter"]');
      var entries = timeline.querySelectorAll(".timeline-entry");
      if (filterInputs.length && entries.length) {
        function applyTimelineFilter() {
          var selected = timeline.querySelector('.filters input[name="timeline-filter"]:checked');
          var kind = selected ? selected.id.slice(2) : "all";
          entries.forEach(function (entry) {
            entry.hidden = kind !== "all" && entry.getAttribute("data-kind") !== kind;
          });
        }
        filterInputs.forEach(function (input) { input.addEventListener("change", applyTimelineFilter); });
        root.classList.add("timeline-filters-ready");
        applyTimelineFilter();
      }
    }

    var button = document.querySelector(".theme-toggle");
    if (!button) return;
    function update() {
      var light = root.dataset.theme === "light";
      button.setAttribute("aria-pressed", light ? "true" : "false");
      button.setAttribute("aria-label", light ? button.getAttribute("data-dark-aria") : button.getAttribute("data-light-aria"));
      button.textContent = light ? button.getAttribute("data-dark-label") : button.getAttribute("data-light-label");
    }
    button.addEventListener("click", function () {
      root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
      update();
      try { window.localStorage.setItem("cv-theme", root.dataset.theme); } catch (ignore) {}
    });
    button.style.display = "inline-flex";
    update();
  });

  // Let details provide no-JavaScript access, with small dismissal helpers.
  document.addEventListener("keydown", function (event) {
    var menu = document.querySelector(".menu-wrap[open]");
    if (event.key === "Escape" && menu) {
      menu.open = false;
      menu.querySelector("summary").focus();
    }
  });
  document.addEventListener("click", function (event) {
    var menu = document.querySelector(".menu-wrap[open]");
    if (menu && !menu.contains(event.target)) menu.open = false;
    if (menu && event.target.closest && event.target.closest(".menu-wrap nav a")) menu.open = false;
  });
}());
