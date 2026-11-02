// Shows a PDF inside the page with PDF.js, so it also works on phones. Pages are drawn as they come into view.
(function () {
  var base = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/";
  function show(box) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = base + "pdf.worker.min.js";
    pdfjsLib.getDocument(new URL(box.dataset.src, location.href).href).promise.then(function (pdf) {
      var seen = new IntersectionObserver(function (items) {
        items.forEach(function (item) {
          if (!item.isIntersecting) return;
          seen.unobserve(item.target);
          pdf.getPage(+item.target.dataset.page).then(function (page) {
            var scale = box.clientWidth * (window.devicePixelRatio || 1) / page.getViewport({ scale: 1 }).width;
            var view = page.getViewport({ scale: scale });
            item.target.width = view.width;
            item.target.height = view.height;
            page.render({ canvasContext: item.target.getContext("2d"), viewport: view });
          });
        });
      }, { rootMargin: "800px" });
      for (var n = 1; n <= pdf.numPages; n++) {
        var c = document.createElement("canvas");
        c.dataset.page = n;
        c.width = 595;
        c.height = 842;
        box.appendChild(c);
        seen.observe(c);
      }
    }).catch(function () {
      box.textContent = "This PDF could not be shown here. Please use the download link above.";
    });
  }
  function start() {
    var box = document.getElementById("rh-pdf");
    if (!box || box.dataset.done) return;
    box.dataset.done = "1";
    if (window.pdfjsLib) return show(box);
    var s = document.createElement("script");
    s.src = base + "pdf.min.js";
    s.onload = function () { show(box); };
    document.head.appendChild(s);
  }
  if (window.document$) document$.subscribe(start); else addEventListener("DOMContentLoaded", start);
})();
