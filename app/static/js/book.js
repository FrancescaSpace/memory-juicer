(function () {
  const pagesEl = document.getElementById('book-pages');
  if (!pagesEl) return;

  const prevBtn = document.getElementById('prev-page');
  const nextBtn = document.getElementById('next-page');
  const indicator = document.getElementById('page-indicator');
  const sheets = Array.from(pagesEl.querySelectorAll('.page-sheet'));
  let index = 0;

  function render() {
    if (indicator) indicator.textContent = (index + 1) + ' / ' + sheets.length;
    if (prevBtn) prevBtn.disabled = index === 0;
    if (nextBtn) nextBtn.disabled = index === sheets.length - 1;
  }

  function go(target) {
    index = Math.max(0, Math.min(sheets.length - 1, target));
    pagesEl.scrollTo({ left: index * pagesEl.clientWidth, behavior: 'smooth' });
    render();
  }

  if (prevBtn) prevBtn.addEventListener('click', function () { go(index - 1); });
  if (nextBtn) nextBtn.addEventListener('click', function () { go(index + 1); });

  let scrollTimer = null;
  pagesEl.addEventListener('scroll', function () {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
      const width = pagesEl.clientWidth || 1;
      index = Math.round(pagesEl.scrollLeft / width);
      render();
    }, 120);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowLeft') go(index - 1);
    if (event.key === 'ArrowRight') go(index + 1);
  });

  render();
})();