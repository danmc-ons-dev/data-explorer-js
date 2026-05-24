class Slideshow extends HTMLElement {
  constructor() {
    super();
  }

  connectedCallback() {
    this.innerHTML = `
        <div class="flex">
            <img class="slideshow object-right mx-auto" src="static/assets/pexels-pixabay-60013.jpg" alt="Heat and Cold" />
            <img class="slideshow mx-auto" src="static/assets/malachi-brooks--HVh7BRp3ls-unsplash.jpg" alt="Wildfires" />
            <img class="slideshow mx-auto" src="static/assets/kelly-sikkema-_whs7FPfkwQ-unsplash.jpg" alt="Flooding" />
            <img class="slideshow object-right mx-auto" src="static/assets/kristen-morith-IWpd8KixceA-unsplash.jpg" alt="Air Pollution" />
            <img class="slideshow mx-auto" src="static/assets/virus-8734360_1280.jpg" alt="Airborne diseases" />
            <img class="slideshow mx-auto" src="static/assets/pexels-helen1-10451829.jpg" alt="Waterborne diseases" />
            <img class="slideshow mx-auto" src="static/assets/pexels-jimbear-2382223.jpg" alt="Vector-borne diseases" />
            <img class="slideshow mx-auto" src="static/assets/pexels-lagosfoodbank-8061688.jpg" alt="Undernutrition" />
            <img class="slideshow mx-auto" src="static/assets/pexels-daniel-reche-718241-3601097.jpg" alt="Mental health" />
            <img class="slideshow mx-auto" src="static/assets/pexels-victormoragriega-28451983.jpg" alt="Chemical contaminants" />
            <img class="slideshow mx-auto" src="static/assets/pexels-cottonbro-7579832.jpg" alt="Healthcare systems and facilities" />
        </div> 
      `;
  }
}

customElements.define('slideshow-component', Slideshow);

let slideIndex = 0;
const slides = document.querySelectorAll('.slideshow');

function showSlides() {
  slides.forEach((slide, index) => {
    slide.classList.remove('active');
    if (index === slideIndex) {
      slide.classList.add('active');
    }
  });
  slideIndex = (slideIndex + 1) % slides.length;
}

setInterval(showSlides, 5000); // Change image every  seconds

window.addEventListener('load', function () {
  showSlides();
});
