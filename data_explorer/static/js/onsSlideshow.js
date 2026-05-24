const ONS_SLIDE_INTERVAL_MS = 5000;

const initialiseOnsSlideshow = (container) => {
  const slides = container.querySelectorAll('.ons-slideshow__slide');
  if (!slides.length) {
    return;
  }

  let slideIndex = 0;

  const setActiveSlide = (index) => {
    slides[slideIndex].classList.remove('active');
    slideIndex = index;
    slides[slideIndex].classList.add('active');
  };

  slides.forEach((slide, index) => {
    if (index === 0) {
      slide.classList.add('active');
    } else {
      slide.classList.remove('active');
    }
  });

  setInterval(() => {
    const nextIndex = (slideIndex + 1) % slides.length;
    setActiveSlide(nextIndex);
  }, ONS_SLIDE_INTERVAL_MS);
};

window.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-js="ons-slideshow"]').forEach(initialiseOnsSlideshow);
});
