(function () {
  var root = document.documentElement;
  var theme = "dark";
  try {
    if (window.localStorage.getItem("cv-theme") === "light") theme = "light";
  } catch (ignore) {}
  root.dataset.theme = theme;

  // Keep the control hidden until it is ready to work.
  document.addEventListener("DOMContentLoaded", function () {
    var button = document.querySelector(".theme-toggle");
    if (!button) return;
    function update() {
      var light = root.dataset.theme === "light";
      button.setAttribute("aria-pressed", light ? "true" : "false");
      button.setAttribute("aria-label", light ? button.getAttribute("data-dark-label") : button.getAttribute("data-light-label"));
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
}());
