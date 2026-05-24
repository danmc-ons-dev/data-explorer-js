class Footer extends HTMLElement {
    constructor() {
      super();
    }
  
    connectedCallback() {
        this.innerHTML = `
          <footer
            class="bg-gray-200"
          >
            <div
              class="flex flex-wrap mx-5 py-3 items-center"
            >

              <div class="flex-shrink-0 mr-12">
                <img
                  src="../static/assets/ONS_Logo_Digital_Colour_English_RGB.png"
                  alt="ONS logo"
                  class="h-10"
                />
              </div>

              <div class="flex-shrink-0 mr-6">
                <img
                  src="../static/assets/AIMS.png"
                  alt="AIMS logo"
                  class="h-12"
                />
              </div>

              <div class="flex-shrink-0 mr-6">
                <img
                  src="../static/assets/RIPS-GHANA.png"
                  alt="RIPS Ghana logo"
                  class="h-16"
                />
              </div>

              <div class="flex flex-col items-center flex-shrink-0 mr-12">
                <img
                  src="../static/assets/wellcome-logo-black.png"
                  alt="Wellcome logo"
                  class="h-20 bg-white"
                />
                <p class="mt-1 font-semibold" style="font-size: 0.41rem;">Funded by Wellcome</p>
              </div>
   
              <div class="flex space-x-3 items-center mr-12">
                <div class="flex-shrink-0">
                  <img
                    src="../static/assets/ogl-symbol-41px-retina-black.png"
                    alt="Open Government Licence logo"
                    class="h-4"
                  />
                </div>

                <div class="text-gray-600">
                  All content is available under the
                  <a
                    class="hover:underline"
                    href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
                    rel="license"
                    >Open Government Licence v3.0 <i class="fa fa-external-link" aria-hidden="true"></i></a
                  >, except where otherwise stated
                </div>
              </div>

              <div class="mr-5 font-medium text-gray-600">
                  <a href="mailto:climate.health@ons.gov.uk" class="hover:underline"
                    >Contact <i class="fa fa-envelope-o" aria-hidden="true"></i></a
                  >
              </div>
            </div>
          </footer>
        `;
    }
  }
  
  customElements.define('footer-component', Footer);
