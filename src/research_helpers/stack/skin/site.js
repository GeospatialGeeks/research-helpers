// Shared with the main site: the same stored light or dark choice, and the small-screen menu.
document.addEventListener("DOMContentLoaded", function () {
  var root = document.documentElement;
  var toggle = document.querySelector("[data-aa-theme]");
  if (toggle) toggle.addEventListener("click", function () {
    var now = root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    var next = now === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  });
  var menu = document.querySelector("[data-aa-menu]");
  var nav = document.getElementById("aa-nav");
  if (menu && nav) menu.addEventListener("click", function () {
    menu.setAttribute("aria-expanded", nav.classList.toggle("open") ? "true" : "false");
  });
});

// Shrink a displayed equation that is too wide for its column, down to three-quarters size. Beyond that it scrolls inside its own box.
function fitEquations() {
  document.querySelectorAll(".md-content mjx-container[display=true]").forEach(function (eq) {
    eq.style.fontSize = "";
    if (eq.scrollWidth > eq.clientWidth + 1) {
      eq.style.fontSize = Math.max(75, Math.floor(100 * eq.clientWidth / eq.scrollWidth)) + "%";
    }
  });
}
window.addEventListener("load", function () {
  if (window.MathJax && MathJax.startup && MathJax.startup.promise) MathJax.startup.promise.then(fitEquations);
});
window.addEventListener("resize", fitEquations);

// Hide or show the side panels, and remember the choice.
document.addEventListener("DOMContentLoaded", function () {
  var root = document.documentElement, button = document.querySelector("[data-aa-sidebar]");
  function set(hidden) {
    root.classList.toggle("aa-panels-hidden", hidden);
    if (button) button.setAttribute("aria-pressed", hidden ? "true" : "false");
    try { localStorage.setItem("panels", hidden ? "hidden" : "shown"); } catch (e) {}
  }
  try { if (localStorage.getItem("panels") === "hidden") set(true); } catch (e) {}
  if (button) button.addEventListener("click", function () { set(!root.classList.contains("aa-panels-hidden")); });
});

// Headings move after the page first lays out (equations typeset, pictures load). The table of contents
// measures heading positions on resize, so tell it once each of those settles; otherwise it marks the wrong section.
(function () {
  var t;
  function remeasure() { clearTimeout(t); t = setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 150); }
  window.addEventListener("load", remeasure);
  document.addEventListener("load", function (e) { if (e.target && e.target.tagName === "IMG") remeasure(); }, true);
  function afterMaths() { if (window.MathJax && MathJax.startup && MathJax.startup.promise) MathJax.startup.promise.then(remeasure); }
  window.addEventListener("load", afterMaths);
  if (window.document$) document$.subscribe(function () { afterMaths(); remeasure(); });
  if (window.ResizeObserver) document.addEventListener("DOMContentLoaded", function () {
    var c = document.querySelector(".md-content"); if (c) new ResizeObserver(remeasure).observe(c);
  });
})();

// Admin edit bar, shared with the main site: ?admin=on shows it on this browser, ?admin=off hides it.
(function () {
  try {
    var q = new URLSearchParams(location.search).get("admin");
    if (q === "on") localStorage.setItem("admin", "1");
    if (q === "off") localStorage.removeItem("admin");
    if (localStorage.getItem("admin") !== "1") return;
  } catch (e) { return; }
  function show() { document.querySelectorAll("[data-admin-edit]").forEach(function (el) { el.hidden = false; }); }
  document.addEventListener("DOMContentLoaded", show);
  if (window.document$) document$.subscribe(show);
})();

// "Report a problem" opens a GitHub issue already filled in with this page's title and address.
document.querySelectorAll("a[data-report]").forEach(function (a) {
  a.addEventListener("click", function () {
    var t = "Problem on: " + document.title, b = "Page: " + location.href.split("#")[0] + "

What is wrong (a broken step, a link, a typo, something unclear):
";
    a.href = a.href.split("?")[0] + "?title=" + encodeURIComponent(t) + "&body=" + encodeURIComponent(b);
  });
});
