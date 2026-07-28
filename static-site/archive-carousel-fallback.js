/* Keep the copied Squarespace case-study carousel usable without its CMS runtime. */
(function () {
  function addFallbackStyles() {
    if (document.getElementById('archive-carousel-fallback-styles')) return;
    const style = document.createElement('style');
    style.id = 'archive-carousel-fallback-styles';
    style.textContent = '.user-items-list-carousel__slides { opacity: 1 !important; }';
    document.head.appendChild(style);
  }

  function set(style, name, value) {
    style.setProperty(name, value, 'important');
  }

  function restoreCarousel(carousel) {
    const track = carousel.querySelector('.user-items-list-carousel__slides');
    if (!track) return;

    set(track.style, 'display', 'flex');
    set(track.style, 'gap', '20px');
    set(track.style, 'overflow-x', 'auto');
    set(track.style, 'scroll-snap-type', 'x mandatory');
    set(track.style, 'scroll-behavior', 'smooth');
    set(track.style, 'transform', 'none');
    set(track.style, 'opacity', '1');

    const slides = Array.from(track.querySelectorAll('.user-items-list-carousel__slide'));
    slides.forEach((slide) => {
      set(slide.style, 'transform', 'none');
      set(slide.style, 'flex', '0 0 calc((100% - 40px) / 3)');
      set(slide.style, 'min-width', '0');
      set(slide.style, 'scroll-snap-align', 'start');
    });

    carousel.querySelectorAll('button').forEach((button) => {
      if (button.dataset.archiveCarouselBound) return;
      button.dataset.archiveCarouselBound = 'true';
      const direction = button.className.includes('--left') ? -1 : 1;
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        track.scrollBy({ left: direction * track.clientWidth, behavior: 'smooth' });
      }, true);
    });
  }

  function restoreAll() {
    document.querySelectorAll('.user-items-list-carousel').forEach(restoreCarousel);
  }

  window.addEventListener('load', () => {
    addFallbackStyles();
    restoreAll();
    window.setTimeout(restoreAll, 250);
    window.setTimeout(restoreAll, 1000);
  });
})();
