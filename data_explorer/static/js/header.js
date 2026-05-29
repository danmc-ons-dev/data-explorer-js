class Header extends HTMLElement {
    constructor() {
      super();
    }
  
    connectedCallback() {
      this.innerHTML = `
        <div class="flex bg-white pt-5 pb-4">

          <!-- ONS Logo -->
          <div class="flex flex-grow flex-shrink-0 ml-5 mt-3 mb-4 md:mb-0">
            <img
              src="../static/assets/ONS_Logo_Digital_Colour_English_RGB.png"
              alt="ONS Logo"
              class="h-9"
            />
          </div>

          <!-- Website Title -->
          <div class="flex flex-col text-center px-3 mb-4 md:mb-0 hidden xl:block">
            <h1 class="text-4xl font-semibold">
              <a href="/">
                <span style="color: #003c57">Climate-Health Platform</span>
              </a>
            </h1>
            <p class="text-lg font-medium text-gray-700">
              Standards for Official Statistics on Climate-Health Interactions
            </p>
          </div>

          <!-- Development Badge -->
          <div class="flex flex-row-reverse flex-grow mt-2.5">
            <div class="flex flex-col mr-5">
              <div class="self-center text-white px-2.5 md:self-start" style="background: #003c57">
                BETA
              </div>
              <div class="font-medium text-gray-700 mt-0.5">Under Development</div>
            </div>
          </div>

        </div>

        <!-- Blue Ribbon Menu -->
        <nav>
          <div class="flex flex-wrap py-1 text-xl text-white text-center" style="background-color: #003c57">
            <div class="flex-none pl-16 pr-6">
              <a
                href="/"
                class="main-tab flex-1"
                >Home</a
              > 
            </div>
            <div class="flex-none px-6">
              <a
                href="framework"
                class="main-tab flex-1"
                >Statistical framework</a
              >
            </div>
            <div class="flex-none px-6">
              <a
                href="indicator_calculators"
                class="main-tab flex-1"
                >Indicator tools</a
              >       
            </div>
            <div class="flex-none px-6">
              <a
                href="about"
                class="main-tab flex-1"
                >About</a
              >
            </div>
            <div class="flex-grow"></div>
            <div class="flex-none">
              <a
                href="https://forms.office.com/pages/responsepage.aspx?id=vweIB4LOiEa84A2BFoTcRmVSElJud0lOvftQQMZLz4pUNFhCQk5PVU40OEpLU0VJTE1BUzJLMkg5MiQlQCN0PWcu&route=shorturl" target="_blank"
                class="flex-1 px-6 hover:underline"
                >Leave feedback &nbsp<i class="fa fa-pencil"></i></a
              >
            </div>
          </div>
        </nav>
      `;
    }
  }
  
  customElements.define('header-component', Header);
