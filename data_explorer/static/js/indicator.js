let groupedDataLineGlobal = {}; // Global variable to store grouped data
let groupedDataBarGlobalRate = {}; // Global variable to store grouped data
let groupedDataBarGlobalDeaths = {}; // Global variable to store grouped data
let groupedDataANAFGlobal = {};
let groupedDataARPMGlobal = {};
let groupedDataARYRGlobal = {};

// Helper functions for UI validation
const getErrorPanel = (target) => {
  const box = typeof target === "string" ? document.getElementById(target) : target;
  if (!box) return { box: null, body: null };

  let body = box.querySelector(".ons-panel__body");
  if (!body) {
    body = document.createElement("div");
    body.className = "ons-panel__body";
    box.appendChild(body);
  }

  // Ensure base/error classes & ARIA
  box.classList.add("ons-panel", "ons-panel--no-title", "ons-panel--error");
  box.setAttribute("role", "alert");

  return { box, body };
};

const showOnsError = (target, message = "Something went wrong.") => {
  const { box, body } = getErrorPanel(target);
  if (!box || !body) return;
  body.textContent = message;
  box.classList.remove("ons-u-d-no");
};

const hideOnsError = (target) => {
  const { box, body } = getErrorPanel(target);
  if (!box || !body) return;
  body.textContent = "";
  box.classList.add("ons-u-d-no");
};

// =============================================================================
// THROTTLING & ERROR HANDLING UTILITIES
// =============================================================================

/**
 * Parse an error response from the API into a structured object.
 * Handles both structured error responses (from api_error_handler.py) and
 * legacy error responses.
 *
 * @param {Response} response - The fetch Response object
 * @returns {Promise<Object>} Parsed error data with error_type, user_message, etc.
 */
const parseErrorResponse = async (response) => {
  try {
    const data = await response.json();
    // Check if this is a structured error response from our error handler
    if (data.error_type) {
      return {
        isStructured: true,
        errorType: data.error_type,
        message: data.message,
        userMessage: data.user_message,
        statusCode: data.status_code || response.status,
        retryAfterSeconds: data.retry_after_seconds || null,
        details: data.details || {},
      };
    }
    // Legacy error format
    return {
      isStructured: false,
      errorType: "unknown",
      message: data.error || data.message || "Unknown error",
      userMessage: data.error || "An error occurred. Please try again.",
      statusCode: response.status,
      retryAfterSeconds: null,
      details: data.details ? { response_preview: data.details } : {},
    };
  } catch (e) {
    // Response wasn't JSON
    return {
      isStructured: false,
      errorType: "unknown",
      message: `HTTP ${response.status}`,
      userMessage: "An unexpected error occurred. Please try again.",
      statusCode: response.status,
      retryAfterSeconds: null,
      details: {},
    };
  }
};

/**
 * Active countdown timers, keyed by target element ID.
 * Used to cancel timers when a new request starts.
 */
const activeCountdowns = {};

/**
 * Cancel any active countdown timer for the given target.
 * @param {string} targetId - The error panel ID
 */
const cancelCountdown = (targetId) => {
  if (activeCountdowns[targetId]) {
    clearInterval(activeCountdowns[targetId]);
    delete activeCountdowns[targetId];
  }
};

/**
 * Display a throttling error with countdown timer.
 * Shows memory stats, countdown to retry, and technical details.
 *
 * @param {Element|string} target - The error panel element or ID
 * @param {Object} errorData - Parsed error data from parseErrorResponse
 */
const showThrottlingError = (target, errorData) => {
  const { box, body } = getErrorPanel(target);
  if (!box || !body) return;

  const targetId = typeof target === "string" ? target : target.id;
  cancelCountdown(targetId);

  let remainingSeconds = errorData.retryAfterSeconds || 60;
  const details = errorData.details || {};

  // Build the initial content
  const updateContent = () => {
    const memoryInfo =
      details.available_mb && details.required_mb
        ? `<p class="ons-u-fs-s ons-u-mt-2xs">Memory: ${details.available_mb} MB available, ${details.required_mb} MB required</p>`
        : "";

    const countdownHtml =
      remainingSeconds > 0
        ? `<p class="ons-u-mt-s"><strong>You can retry in ${remainingSeconds} second${remainingSeconds !== 1 ? "s" : ""}</strong></p>`
        : `<p class="ons-u-mt-s" style="color: #0f7b0f;"><strong>You can now retry your request.</strong></p>`;

    body.innerHTML = `
      <p><strong>${errorData.userMessage}</strong></p>
      ${memoryInfo}
      ${countdownHtml}
      <details class="ons-u-mt-s">
        <summary class="ons-u-fs-s" style="cursor: pointer;">Technical details</summary>
        <pre class="ons-u-fs-xs ons-u-mt-2xs" style="white-space: pre-wrap; background: #f5f5f5; padding: 8px; border-radius: 4px;">${JSON.stringify(details, null, 2)}</pre>
      </details>
    `;
  };

  updateContent();
  box.classList.remove("ons-u-d-no");

  // Start countdown
  if (remainingSeconds > 0) {
    activeCountdowns[targetId] = setInterval(() => {
      remainingSeconds--;
      updateContent();
      if (remainingSeconds <= 0) {
        cancelCountdown(targetId);
      }
    }, 1000);
  }
};

/**
 * Display a file-too-large error (permanent failure).
 * No countdown timer since retrying won't help.
 *
 * @param {Element|string} target - The error panel element or ID
 * @param {Object} errorData - Parsed error data from parseErrorResponse
 */
const showFileTooLargeError = (target, errorData) => {
  const { box, body } = getErrorPanel(target);
  if (!box || !body) return;

  const targetId = typeof target === "string" ? target : target.id;
  cancelCountdown(targetId);

  const details = errorData.details || {};

  const memoryInfo =
    details.required_mb && details.total_mb
      ? `<p class="ons-u-fs-s ons-u-mt-2xs">Your request requires ${details.required_mb} MB, but the server maximum is ${details.total_mb} MB.</p>`
      : "";

  const excessInfo = details.excess_mb
    ? `<p class="ons-u-fs-s ons-u-mt-2xs">Please reduce your data by approximately ${details.excess_mb} MB.</p>`
    : "";

  body.innerHTML = `
    <p><strong>${errorData.userMessage}</strong></p>
    ${memoryInfo}
    ${excessInfo}
    <p class="ons-u-mt-s ons-u-fs-s">Suggestions:</p>
    <ul class="ons-u-fs-s ons-u-mt-2xs">
      <li>Filter to fewer rows or a smaller time range</li>
      <li>Remove unnecessary columns</li>
      <li>Split your data into smaller batches</li>
    </ul>
    <details class="ons-u-mt-s">
      <summary class="ons-u-fs-s" style="cursor: pointer;">Technical details</summary>
      <pre class="ons-u-fs-xs ons-u-mt-2xs" style="white-space: pre-wrap; background: #f5f5f5; padding: 8px; border-radius: 4px;">${JSON.stringify(details, null, 2)}</pre>
    </details>
  `;
  box.classList.remove("ons-u-d-no");
};

/**
 * Enhanced showOnsError that handles both simple strings and structured errors.
 * Routes to specialized handlers for throttling and file-too-large errors.
 *
 * @param {Element|string} target - The error panel element or ID
 * @param {string|Object} messageOrData - Error message string OR structured error data
 */
const showOnsErrorEnhanced = (target, messageOrData) => {
  // If it's a simple string, use the original behavior
  if (typeof messageOrData === "string") {
    const { box, body } = getErrorPanel(target);
    if (!box || !body) return;
    const targetId = typeof target === "string" ? target : target.id;
    cancelCountdown(targetId);
    body.textContent = messageOrData;
    box.classList.remove("ons-u-d-no");
    return;
  }

  // It's a structured error object
  const errorData = messageOrData;

  switch (errorData.errorType) {
    case "throttling":
      showThrottlingError(target, errorData);
      break;
    case "file_too_large":
      showFileTooLargeError(target, errorData);
      break;
    default:
      // For other error types, show user message with details
      const { box, body } = getErrorPanel(target);
      if (!box || !body) return;
      const targetId = typeof target === "string" ? target : target.id;
      cancelCountdown(targetId);
      body.innerHTML = `
        <p><strong>${errorData.userMessage}</strong></p>
        ${errorData.details?.response_preview ? `<details class="ons-u-mt-s"><summary class="ons-u-fs-s" style="cursor: pointer;">Technical details</summary><pre class="ons-u-fs-xs ons-u-mt-2xs" style="white-space: pre-wrap; background: #f5f5f5; padding: 8px; border-radius: 4px;">${errorData.details.response_preview}</pre></details>` : ""}
      `;
      box.classList.remove("ons-u-d-no");
  }
};

// Multi-select helpers
const getMultiSelectValues = (name) => {
  const elements = document.getElementsByName(name);
  return Array.from(elements).map((element) => element.value);
};

// Checkbox helpers
const getCheckboxValues = (containerId) => {
  const container = document.getElementById(containerId);
  if (!container) return [];

  const selectedInputs = container.querySelectorAll(
    ".ons-checkbox.ons-checkbox--selected input[type='checkbox']",
  );

  return Array.from(selectedInputs).map((input) => input.value);
};

// Generic DOM helpers
const getEl = (id) => document.getElementById(id);

const on = (id, event, handler) => {
  const el = getEl(id);
  if (!el) return null;
  el.addEventListener(event, handler);
  return el;
};

const getValue = (id) => {
  const el = getEl(id);
  return el && typeof el.value === "string" ? el.value.trim() : "";
};

const getFile = (id) => {
  const el = getEl(id);
  return el && el.files ? el.files[0] : null;
};

const getNumber = (id) => {
  const v = getValue(id);
  if (v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
};

function schedulePlotResize(targetEl) {
  if (!targetEl) return;
  requestAnimationFrame(() => {
    if (window.Plotly && Plotly.Plots && typeof Plotly.Plots.resize === "function") {
      Plotly.Plots.resize(targetEl);
    }
  });
}

function resizeVectorbornePlots() {
  ["vectorCurveDiv", "vectorBarDiv", "vectorScatterDiv"].forEach((id) => {
    const el = document.getElementById(id);
    if (el && el.children.length) {
      schedulePlotResize(el);
    }
  });
}

function renderONSCheckboxes(containerId, columns, { name, label }) {
  const wrapper = document.getElementById(containerId);
  if (!wrapper) return;
  wrapper.innerHTML = "";

  if (label) {
    const legend = document.createElement("p");
    legend.className = "ons-u-fs-r--b";
    legend.textContent = label;
    wrapper.appendChild(legend);
  }

  const items = document.createElement("div");
  items.className = "ons-checkboxes__items";

  columns.forEach((column, index) => {
    if (!column) return;

    const item = document.createElement("span");
    item.className = "ons-checkboxes__item";

    const checkboxWrapper = document.createElement("span");
    checkboxWrapper.className = "ons-checkbox";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "ons-checkbox__input ons-js-checkbox";
    checkbox.id = `${containerId}-${index}`;
    checkbox.name = name;
    checkbox.value = column;

    // Toggle selected state on click
    checkbox.addEventListener("click", () => {
      checkboxWrapper.classList.toggle("ons-checkbox--selected");
    });

    const checkboxLabel = document.createElement("label");
    checkboxLabel.className = "ons-checkbox__label";
    checkboxLabel.setAttribute("for", checkbox.id);
    checkboxLabel.textContent = column;

    checkboxWrapper.appendChild(checkbox);
    checkboxWrapper.appendChild(checkboxLabel);
    item.appendChild(checkboxWrapper);
    items.appendChild(item);
  });

  wrapper.appendChild(items);
  wrapper.classList.remove("ons-u-d-no");
}

async function plotAPIOnMap(responseShp) {
  // Add basemap and paired region shapefile to each map
  const mapOne = L.map("map1").setView([53, -1], 5);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(mapOne);

  L.geoJson(JSON.parse(responseShp), {
    style: styleOne,
    onEachFeature: onEachFeatureOne,
  }).addTo(mapOne);

  const mapTwo = L.map("map2").setView([53, -1], 5);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(mapTwo);

  L.geoJson(JSON.parse(responseShp), {
    style: styleTwo,
    onEachFeature: onEachFeatureTwo,
  }).addTo(mapTwo);

  // Get color and label pairs for each map
  let colorLabelPairsOne = [];
  JSON.parse(responseShp).features.forEach(function (feature) {
    colorLabelPairsOne.push({
      color: feature.properties.color_hc,
      label: feature.properties.perc_hc_label,
      val: feature.properties.high_cold,
    });
  });

  let colorLabelPairsTwo = [];
  JSON.parse(responseShp).features.forEach(function (feature) {
    colorLabelPairsTwo.push({
      color: feature.properties.color_hh,
      label: feature.properties.perc_hh_label,
      val: feature.properties.high_heat,
    });
  });

  // Get unique color and label pairs
  colorLabelPairsOne = colorLabelPairsOne.filter(
    (value, index, self) =>
      index === self.findIndex((t) => t.label === value.label && t.color === value.color),
  );

  colorLabelPairsTwo = colorLabelPairsTwo.filter(
    (value, index, self) =>
      index === self.findIndex((t) => t.label === value.label && t.color === value.color),
  );

  // Sort unique color and label pairs
  colorLabelPairsOne
    .sort(function (a, b) {
      return a.val - b.val;
    })
    .reverse();

  colorLabelPairsTwo
    .sort(function (a, b) {
      return a.val - b.val;
    })
    .reverse();

  // Add legend to each map
  let legendOne = L.control({ position: "bottomright" });
  legendOne.onAdd = function (map) {
    let div = L.DomUtil.create("div", "legend bg-white bg-opacity-80 items-center");
    let itemDiv = L.DomUtil.create("div", "legend");
    itemDiv.innerHTML += "<p>Quartile Data</p>";
    div.appendChild(itemDiv);
    colorLabelPairsOne.forEach(function (pair) {
      itemDiv.innerHTML += '<i style="background:' + pair.color + '"></i> ' + pair.label + "<br>";
      div.appendChild(itemDiv);
    });
    return div;
  };

  let legendTwo = L.control({ position: "bottomright" });
  legendTwo.onAdd = function (map) {
    let div = L.DomUtil.create("div", "legend bg-white bg-opacity-80 items-center");
    let itemDiv = L.DomUtil.create("div", "legend");
    itemDiv.innerHTML += "<p>Quartile Data</p>";
    div.appendChild(itemDiv);
    colorLabelPairsTwo.forEach(function (pair) {
      itemDiv.innerHTML += '<i style="background:' + pair.color + '"></i> ' + pair.label + "<br>";
      div.appendChild(itemDiv);
    });
    return div;
  };

  legendOne.addTo(mapOne);
  legendTwo.addTo(mapTwo);

  const selectedYear = document.getElementById("outputYear").value;
  // const selectedYear = new Date(dropdownDate.value).getFullYear();
  const outputYearGraph = selectedYear == "" ? "" : "(" + selectedYear + ")";

  let titleOne = L.control({ position: "topright" });
  titleOne.onAdd = function (map) {
    let div = L.DomUtil.create("div", "mapTitle");
    div.className = "bg-white bg-opacity-80 px-1 py-1";
    div.innerHTML = `<h1 class = "font-bold text-lg">Cold-related mortality rate per 100k ${outputYearGraph}</h1>`;
    return div;
  };

  let titleTwo = L.control({ position: "topright" });
  titleTwo.onAdd = function (map) {
    let div = L.DomUtil.create("div", "mapTitle");
    div.className = "bg-white bg-opacity-80 px-1 py-1";
    div.innerHTML = `<h1 class = "font-bold text-lg">Heat-related mortality rate per 100k ${outputYearGraph}</h1>`;
    return div;
  };

  titleOne.addTo(mapOne);
  titleTwo.addTo(mapTwo);

  // Add printer button to each map
  // Class in CSS - not working
  let a3Size = {
    width: 2339,
    height: 3308,
    className: "a3CssClass",
    tooltip: "A custom A3 size",
  };

  let printerOne = L.easyPrint({
    tileLayer: "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png",
    sizeModes: ["Current"],
    filename: "relative_risk_map",
    exportOnly: true,
    hideControlContainer: false,
    hideClasses: ["leaflet-control-zoom"],
  }).addTo(mapOne);

  let printerTwo = L.easyPrint({
    tileLayer: "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png",
    sizeModes: ["Current"],
    filename: "attributable_rate_map",
    exportOnly: true,
    hideControlContainer: false,
    hideClasses: ["leaflet-control-zoom"],
  }).addTo(mapTwo);
}

// show/hide divs on checkbox
function DoCheckUncheckDisplay(d, dchecked) {
  if (d.checked == true) {
    document.getElementById(dchecked).style.display = "block";
  } else {
    document.getElementById(dchecked).style.display = "none";
  }
}

// Apply the color to each feature
function styleOne(feature) {
  return {
    fillColor: feature.properties.color_hc,
    weight: 1,
    opacity: 1,
    color: "black",
    fillOpacity: 0.7,
  };
}

// Apply the color to each feature
function styleTwo(feature) {
  return {
    fillColor: feature.properties.color_hh,
    weight: 1,
    opacity: 1,
    color: "black",
    fillOpacity: 0.7,
  };
}

// Set interactivity for map one
function onEachFeatureOne(feature, layer) {
  layer.setStyle(styleOne(feature));

  // Mouseover event
  if (feature.properties) {
    layer.on({
      mouseover: function (e) {
        this.setStyle({
          weight: 3,
          color: "black",
          fillOpacity: 0.7,
        });
        if (!L.Browser.ie && !L.Browser.opera) {
          this.bringToFront();
        }

        let popupContent = `
        <div class="bg-slate-500 rounded">
            <h2 class="text-md font-bold">${feature.properties.RGN22NM}</h2>
            <h2 class="text-md">Cold-related mortality rate per 100k: ${feature.properties.high_cold}</h2>
        </div>`;

        this.bindPopup(popupContent).openPopup();
      },
      mouseout: function (e) {
        this.setStyle(styleOne(feature)); // Reset to original style
      },
    });
  }
}

// Set interactivity for map two
function onEachFeatureTwo(feature, layer) {
  layer.setStyle(styleTwo(feature));

  // Mouseover event
  if (feature.properties) {
    layer.on({
      mouseover: function (e) {
        this.setStyle({
          weight: 3,
          color: "black",
          fillOpacity: 0.7,
        });
        if (!L.Browser.ie && !L.Browser.opera) {
          this.bringToFront();
        }

        let popupContent = `
        <div class="bg-slate-500 rounded">
            <h2 class="text-md font-bold">${feature.properties.RGN22NM}</h2>
            <h2 class="text-md">Heat-related mortality rate per 100k: ${feature.properties.high_heat}</h2>
        </div>`;

        this.bindPopup(popupContent).openPopup();
      },
      mouseout: function (e) {
        this.setStyle(styleTwo(feature)); // Reset to original style
      },
    });
  }
}

// Get data from API for plotting for Relative Risk Heat and Cold
function getRelRiskAPIOutput(relRiskAPIOutput, groupColumn) {
  let groupedDataLine = {};

  for (let row of relRiskAPIOutput) {
    const group = row[groupColumn];
    if (!groupedDataLine[group]) {
      groupedDataLine[group] = {
        temperature: [],
        relativeRisk: [],
        upper: [],
        lower: [],
        optimalLower: [],
        optimalHigher: [],
      };
    }
    groupedDataLine[group].temperature.push(row["temp"]);
    groupedDataLine[group].relativeRisk.push(row["rel_risk"]);
    groupedDataLine[group].upper.push(row["upper"]);
    groupedDataLine[group].lower.push(row["lower"]);
    groupedDataLine[group].optimalLower.push(row["optimal_temp_range_min"]);
    groupedDataLine[group].optimalHigher.push(row["optimal_temp_range_max"]);
  }

  groupedDataLineGlobal = groupedDataLine; // Store the grouped data in global variable
}

// Reformat API response for Wildfires (RR)
function reformatWildfiresRR(apiOutput) {
  let groupedDataLine = {};

  for (let row of apiOutput) {
    let group = row["region_name"];
    if (group === undefined) group = "Full Dataset";
    if (!groupedDataLine[group]) {
      groupedDataLine[group] = {
        relativeRisk: [],
        upper: [],
        lower: [],
        lag: [],
      };
    }
    groupedDataLine[group].relativeRisk.push(row["relative_risk"]);
    groupedDataLine[group].upper.push(row["ci_upper"]);
    groupedDataLine[group].lower.push(row["ci_lower"]);
    groupedDataLine[group].lag.push(row["lag"]);
  }

  groupedDataLineGlobal = groupedDataLine; // Store the grouped data in global variable
}

// Reformat API response for Wildfires (AN/AR)
function reformatWildfiresANAF(apiOutput) {
  if (!Array.isArray(apiOutput)) {
    console.error("reformatWildfiresANAF expected an array, got:", apiOutput);
    groupedDataANAFGlobal = {};
    return;
  }

  const groupedDataANAF = {};

  for (const row of apiOutput) {
    const group = row.region;
    if (!groupedDataANAF[group]) {
      groupedDataANAF[group] = {
        // AF (number)
        upper_af: [],
        lower_af: [],
        af: [],
        // AN (number)
        upper_an: [],
        lower_an: [],
        an: [],
        // AR (rate per 100k)
        upper_rate: [],
        lower_rate: [],
        rate: [],
        // time
        year: [],
        month: [],
      };
    }

    const g = groupedDataANAF[group];

    // Fractions
    g.upper_af.push(row.upper_ci_attributable_fraction);
    g.lower_af.push(row.lower_ci_attributable_fraction);
    g.af.push(row.average_attributable_fraction);

    // Attributable number
    g.upper_an.push(row.upper_ci_attributable_number);
    g.lower_an.push(row.lower_ci_attributable_number);
    g.an.push(row.total_attributable_number);

    // Attributable rate (deaths per 100k)
    g.rate.push(row.deaths_per_100k);
    g.upper_rate.push(row.upper_ci_deaths_per_100k);
    g.lower_rate.push(row.lower_ci_deaths_per_100k);

    // Time
    g.year.push(row.year);
    g.month.push(row.month);
  }

  groupedDataANAFGlobal = groupedDataANAF;
}

// Reformat API response for Wildfires bar chart (Deaths & PM2.5)
function reformatWildfiresARPM(apiOutput) {
  const groupedDataARPM = {};

  for (const row of apiOutput) {
    const region = row.region;
    if (!groupedDataARPM[region]) {
      groupedDataARPM[region] = {
        months: [],
        deathsPer100k: [],
        meanPm: [],
      };
    }

    groupedDataARPM[region].months.push(row.month_name);
    groupedDataARPM[region].deathsPer100k.push(row.mean_deaths_per_100k);
    groupedDataARPM[region].meanPm.push(row.mean_pm);
  }

  groupedDataARPMGlobal = groupedDataARPM;
}

// Get data from API for plotting for Relative Risk Mental Health
function getRelRiskAPIOutputMH(relRiskAPIOutput, groupColumn) {
  let groupedDataLine = {};

  for (let row of relRiskAPIOutput) {
    const group = row[groupColumn];
    if (!groupedDataLine[group]) {
      groupedDataLine[group] = {
        temperature: [],
        relativeRisk: [],
        upper: [],
        lower: [],
      };
    }
    groupedDataLine[group].temperature.push(row["Temperature"]);
    groupedDataLine[group].relativeRisk.push(row["RRfit"]);
    groupedDataLine[group].upper.push(row["RRhigh"]);
    groupedDataLine[group].lower.push(row["RRlow"]);

    groupedDataLineGlobal = groupedDataLine; // Store the grouped data in global variable
  }
}

function getAttrRateAPIOutput(attrRateAPIOutput) {
  let groupedDataBarRate = {};

  for (let row of attrRateAPIOutput) {
    let group = row["_row"];
    if (group === "aggregated") {
      group = "all_regions";
    }
    if (!groupedDataBarRate[group]) {
      groupedDataBarRate[group] = {
        region: [],
        highHeat: [],
        highCold: [],
        highHeatUpper: [],
        highHeatLower: [],
        highColdUpper: [],
        highColdLower: [],
      };
    }
    groupedDataBarRate[group].region.push(row["_row"]);
    groupedDataBarRate[group].highHeat.push(row["high_heat"]);
    groupedDataBarRate[group].highCold.push(row["high_cold"]);
    groupedDataBarRate[group].highHeatUpper.push(row["high_heat_ci_97.5"]);
    groupedDataBarRate[group].highHeatLower.push(row["high_heat_ci_2.5"]);
    groupedDataBarRate[group].highColdUpper.push(row["high_cold_ci_97.5"]);
    groupedDataBarRate[group].highColdLower.push(row["high_cold_ci_2.5"]);
  }

  groupedDataBarGlobalRate = groupedDataBarRate; // Store the grouped data in global variable
}

// Get data from API for plotting for Attributable Deaths
function getAttrDeathsAPIOutput(attrDeathsAPIOutput) {
  let groupedDataBarDeaths = {};

  for (let row of attrDeathsAPIOutput) {
    let group = row["_row"];
    if (group === "aggregated") {
      group = "all_regions";
    }
    if (!groupedDataBarDeaths[group]) {
      groupedDataBarDeaths[group] = {
        region: [],
        highHeat: [],
        highCold: [],
        highHeatUpper: [],
        highHeatLower: [],
        highColdUpper: [],
        highColdLower: [],
      };
    }

    groupedDataBarDeaths[group].region.push(row["_row"]);
    groupedDataBarDeaths[group].highHeat.push(row["high_heat"]);
    groupedDataBarDeaths[group].highCold.push(row["high_cold"]);
    groupedDataBarDeaths[group].highHeatUpper.push(row["high_heat_ci_97.5"]);
    groupedDataBarDeaths[group].highHeatLower.push(row["high_heat_ci_2.5"]);
    groupedDataBarDeaths[group].highColdUpper.push(row["high_cold_ci_97.5"]);
    groupedDataBarDeaths[group].highColdLower.push(row["high_cold_ci_2.5"]);
  }

  groupedDataBarGlobalDeaths = groupedDataBarDeaths; // Store the grouped data in global variable
}

function arrayToCSV(arr) {
  return arr.map((row) => row.map(String).join(",")).join("\n");
}

// Populate the dropdown with regions
function populateDropdownWithRegion(groupedData, dropdownId) {
  // Populate dropdown with group names
  const dropdown = document.getElementById(dropdownId);
  dropdown.innerHTML = ""; // Clear previous options
  for (let group in groupedData) {
    const option = document.createElement("option");
    option.value = group;
    option.text = group;
    dropdown.appendChild(option);
  }
}

function t0populateDropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "t0ColDistCols",
        "t0maColsList",
        "t0DepColName",
        "t0IndColName",
        "t0DateCol",
        "t0AggCol",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);
        // Populate the dropdown with CSV columns
        columns.forEach((column) => {
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;

              dropdown.dispatchEvent(new Event("change"));
            }
            dropdown.add(option);
          }
        });
      });
      document.querySelectorAll("[data-multi-select]").forEach((select) => new MultiSelect(select));
    },
  });
}

// Get columns for dropdown from uploaded CSV
function populateDropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "deathsCol",
        "t1dateCol",
        "tempCol",
        "popCol",
        "subgeoCol",
        "ind1Col",
        "ind2Col",
        "ind3Col",
        "ind4Col",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);

        switch (dropdownId) {
          case "deathsCol":
            dropdown.innerHTML =
              '<option value="">Select the column containing daily death counts</option>';
            break;

          case "t1dateCol":
            dropdown.innerHTML =
              '<option value="">Select the date column (format yyyy-mm-dd)</option>';
            break;

          case "tempCol":
            dropdown.innerHTML = '<option value="">Select daily mean or max temp column</option>';
            break;

          case "popCol":
            dropdown.innerHTML =
              '<option value="">Select the column containing population counts</option>';
            break;

          case "subgeoCol":
            dropdown.innerHTML =
              '<option value="">Select the column of sub-geographies if required</option>';
            let option = document.createElement("option");
            option.value = "";
            option.text = "-- None --";
            option.disabled;
            dropdown.add(option);
            break;

          case "ind1Col":
            dropdown.innerHTML = '<option value="">No column selected</option>';
            break;

          case "ind2Col":
            dropdown.innerHTML = '<option value="">No column selected</option>';
            break;

          case "ind3Col":
            dropdown.innerHTML = '<option value="">No column selected</option>';
            break;

          case "ind4Col":
            dropdown.innerHTML = '<option value="">No column selected</option>';
            break;

          default:
            console.error("Dropdown not found:", dropdownId);
            return; // Skip to the next dropdownId
        }

        // Populate the dropdown with CSV columns
        let selectedColumn = null;
        columns.forEach((column) => {
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;
              selectedColumn = column;
            }
            dropdown.add(option);
          }
        });
        // After all options are added, set dropdown value if a match was found
        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
    },
  });
}

// Get columns for dropdown from uploaded CSV
function populateT2DropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "date_col",
        "region_col",
        "mean_temperature_col",
        "health_outcome_col",
        "pm_25_col",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);

        // Populate the dropdown with CSV columns
        let selectedColumn = null;
        columns.forEach((column) => {
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;
              selectedColumn = column;
            }
            dropdown.add(option);
          }
        });
        // After all options are added, set dropdown value if a match was found
        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
    },
  });
}

// Get columns for dropdown from uploaded CSV
function populateT7DropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "t7timeCol",
        "t7geographyCol",
        "t7tempCol",
        "t7healthOutcomeCol",
        "t7popCol",
        "t7IndependentColList",
        "t7ControlColList",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);

        switch (dropdownId) {
          case "t7timeCol":
            dropdown.innerHTML =
              '<option value="">Select the date column (format yyyy-mm-dd)</option>';
            break;

          case "t7geographyCol":
            dropdown.innerHTML =
              '<option value="">Select column containing region data if required';
            break;

          case "t7tempCol":
            dropdown.innerHTML = '<option value="">Select daily mean or max temp column</option>';
            break;

          case "t7healthOutcomeCol":
            dropdown.innerHTML =
              '<option value="">Select the column containing the health outcome</option>';
            break;

          case "t7popCol":
            dropdown.innerHTML =
              '<option value="">Select the column containing the population</option>';
            break;

          case "t7ControlColList":
          case "t7IndependentColList":
            break;

          default:
            console.error("Dropdown not found:", dropdownId);
            return; // Skip to the next dropdownId
        }

        // Populate the dropdown with CSV columns
        let selectedColumn = null;
        columns.forEach((column) => {
          if (dropdownId === "t7IndependentColList" || dropdownId === "t7ControlColList") {
            renderONSCheckboxes(dropdownId, columns, {
              name:
                dropdownId === "t7IndependentColList"
                  ? "t7IndependentColList[]"
                  : "t7ControlColList[]",
            });
            return;
          }
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;
              selectedColumn = column;
            }
            dropdown.add(option);
          }
        });
        // After all options are added, set dropdown value if a match was found
        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
      document.querySelectorAll(".checkbox-collapsible").forEach((el) => {
        el.classList.remove("ons-u-vh");
        el.hidden = false;
      });
    },
  });
}

// Get columns for dropdown from uploaded CSV (Air pollution)
function populateT8DropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      const columns = results.data[0] || [];

      // dropdown id -> substring(s) in the column header that should auto-select
      const dropdownTargets = {
        t8date_col: ["date"],
        t8region_col: ["region", "province", "area"],
        t8pm25_col: ["pm25", "pm2.5", "pm_25"],
        t8deaths_col: ["deaths", "mortality"],
        t8population_col: ["population", "pop"],
        t8humidity_col: ["humidity", "rh"],
        t8precipitation_col: ["precipitation", "rainfall", "precip"],
        t8tmax_col: ["tmax", "max_temp"],
        t8wind_speed_col: ["wind_speed", "wind"],
      };

      Object.entries(dropdownTargets).forEach(([dropdownId, hints]) => {
        const dropdown = document.getElementById(dropdownId);
        if (!dropdown) return;

        // Reset to placeholder option only
        const placeholder = dropdown.querySelector('option[value=""]');
        dropdown.innerHTML = "";
        if (placeholder) dropdown.appendChild(placeholder);

        let selectedColumn = null;
        columns.forEach((column) => {
          if (!column) return;
          const option = document.createElement("option");
          option.value = column;
          option.text = column;
          const colLower = column.toLowerCase();
          if (!selectedColumn && hints.some((h) => colLower.includes(h))) {
            option.selected = true;
            selectedColumn = column;
          }
          dropdown.add(option);
        });

        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
    },
  });
}

// Populate diarrhea dropdowns
function populateT4HealthDropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "t4region",
        "t4district",
        "t4date",
        "t4year",
        "t4month",
        "t4diarrhea_case",
        "t4tot_pop",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);
        let selectedColumn = null;
        columns.forEach((column) => {
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;
              selectedColumn = column;
            }
            dropdown.add(option);
          }
        });
        // After all options are added, set dropdown value if a match was found
        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
    },
  });
}

// Populate diarrhea dropdowns
function populateT4ClimateDropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "t4tmin",
        "t4tmean",
        "t4tmax",
        "t4rainfall",
        "t4r_humidity",
        "t4runoff",
        "t4spi",
        "t4basisMatricesList",
        "t4inlaParamsList",
        "t4param_term",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);
        // Populate the dropdown with CSV columns
        let selectedColumn = null;
        columns.forEach((column) => {
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;
              selectedColumn = column;
            }
            dropdown.add(option);
          }
        });
        // After all options are added, set dropdown value if a match was found
        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
      document.querySelectorAll("[data-multi-select]").forEach((select) => new MultiSelect(select));
    },
  });
}

// Populate diarrhea dropdowns
function populateT5HealthDropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "t5region",
        "t5district",
        "t5date",
        "t5year",
        "t5month",
        "t5malaria_case",
        "t5tot_pop",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);
        // Populate the dropdown with CSV columns
        let selectedColumn = null;
        columns.forEach((column) => {
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;
              selectedColumn = column;
            }
            dropdown.add(option);
          }
        });
        // After all options are added, set dropdown value if a match was found
        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
    },
  });
}

// Populate diarrhea dropdowns
function populateT5ClimateDropdownWithCSV(file) {
  Papa.parse(file, {
    skipEmptyLines: true,
    complete: function (results) {
      let columns = results.data[0]; // Assuming the first row contains column headers

      // Array of dropdown IDs
      let dropdownIds = [
        "t5tmin",
        "t5tmean",
        "t5tmax",
        "t5rainfall",
        "t5r_humidity",
        "t5runoff",
        "t5spi",
        "t5ndvi",
        "t5basisMatricesList",
        "t5inlaParamsList",
        "t5param_term",
      ];

      // Loop through each dropdown ID
      dropdownIds.forEach((dropdownId) => {
        let dropdown = document.getElementById(dropdownId);
        // Populate the dropdown with CSV columns
        let selectedColumn = null;
        columns.forEach((column) => {
          if (dropdownId === "t5basisMatricesList" || dropdownId === "t5inlaParamsList") {
            renderONSCheckboxes(dropdownId, columns, {
              name:
                dropdownId === "t5basisMatricesList"
                  ? "t5basisMatricesList[]"
                  : "t5inlaParamsList[]",
            });
            return;
          }
          if (column !== "") {
            let option = document.createElement("option");
            option.value = column;
            option.text = column;
            // If the column name (lowercase) is in the dropdown ID, set as selected
            if (dropdownId.toLowerCase().includes(column.toLowerCase())) {
              option.selected = true;
              selectedColumn = column;
            }
            dropdown.add(option);
          }
        });
        // After all options are added, set dropdown value if a match was found
        if (selectedColumn !== null) {
          dropdown.value = selectedColumn;
          dropdown.dispatchEvent(new Event("change"));
        }
      });
      document.querySelectorAll("[data-multi-select]").forEach((select) => new MultiSelect(select));
      document.querySelectorAll(".checkbox-collapsible").forEach((el) => {
        el.classList.remove("ons-u-vh");
        el.hidden = false;
      });
    },
  });
}

// Load geojson and get countries for dropdown
function populateDropdownWithGJSON(columnName) {
  let dropdown = document.getElementById(columnName);

  fetch("/static/data/shp/countries_incl_uk.geojson")
    .then((response) => response.json())
    .then((data) => {
      data.features.forEach((feature) => {
        let option = document.createElement("option");
        option.value = feature.properties.COUNTRY;
        option.textContent = feature.properties.COUNTRY;
        dropdown.appendChild(option);
      });
    })
    .catch((error) => console.error("Error fetching the GeoJSON:", error));
}

function parseDate(dateStr) {
  // Try YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [year, month, day] = dateStr.split("-");
    return new Date(year, month - 1, day);
  }
  // Try DD/MM/YYYY
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(dateStr)) {
    const [day, month, year] = dateStr.split("/");
    return new Date(year, month - 1, day);
  }
  // Fallback
  return new Date(dateStr);
}

function updateDateRange(file, columnName) {
  Papa.parse(file, {
    header: true,
    skipEmptyLines: true,
    complete: function (results) {
      const dates = results.data
        .map((row) => {
          const dateStr = row[columnName];
          const date = parseDate(dateStr);
          return isNaN(date.getTime()) ? null : date;
        })
        .filter(Boolean); // Remove any nulls
      if (dates.length > 0) {
        const maxDate = new Date(Math.max.apply(null, dates));
        const minDate = new Date(Math.min.apply(null, dates));

        // Convert date object to ISO datetime string, get first element (yyyy-mm-dd)
        dataMaxYear = new Date(maxDate).getFullYear();
        dataMinYear = new Date(minDate).getFullYear();

        const outputYearEl = getEl("outputYear");
        if (outputYearEl) {
          outputYearEl.value = dataMaxYear;
        }
      } else {
        alert(
          "No valid dates found in the selected column. Please check your date format is YYYY-MM-DD.",
        );
      }
    },
  });
}

// Plot line chart for Heat and Cold based on dropdown selection
function plotLine() {
  // Get Date Range
  const selectedYear = document.getElementById("outputYear").value;
  const selectDist = document.getElementById("rrDistLength").value;
  let firstYear = dataMinYear;
  if (String(selectDist) != "0") {
    firstYear = Number(selectedYear) - Number(selectDist);
  }
  outputYearGraph = selectedYear == "" ? "" : "(" + selectedYear + ")";

  // Get Geography
  const dropdown = document.getElementById("groupDropdown");
  const selectedGroup = dropdown.value;

  const data = groupedDataLineGlobal[selectedGroup];

  document.getElementById("output_region_plot").textContent = selectedGroup;

  // Get MMT
  const minValue = Math.min(...data.relativeRisk);
  const minIndex = data.relativeRisk.indexOf(minValue);
  const MinMortalityTemp = data.temperature[minIndex];

  // Get Additional Plot Options
  const colouredLines = document.getElementById("mmtBasedLine").checked;
  const plotOTR = document.getElementById("plotOTR").checked;
  const plotMMT = document.getElementById("plotMMT").checked;

  // Get Data for All
  const xAll = data.temperature;
  const yUpper = data.upper;
  const yLower = data.lower;

  // Get Data for MMT coloured lines
  const xBelow = data.temperature.slice(0, minIndex + 1);
  const yBelow = data.relativeRisk.slice(0, minIndex + 1);
  const xAbove = data.temperature.slice(minIndex);
  const yAbove = data.relativeRisk.slice(minIndex);

  // Get OTR
  const optimalLower = data.optimalLower.slice(0, 1)[0];
  const optimalHigher = data.optimalHigher.slice(0, 1)[0];

  // Plot Main Line
  let coldLine = {};
  let heatLine = {};
  let mainLine = {};
  let ciFill = "rgba(68, 68, 68, 0.3)";

  if (!colouredLines) {
    mainLine = {
      x: data.temperature,
      y: data.relativeRisk,
      type: "scatter",
      mode: "lines",
      name: `${selectedGroup}`,
      line: { color: "#1f9282", width: 6 },
    };
    ciFill = "rgba(31, 146, 130, 0.3)";
  } else {
    coldLine = {
      x: xBelow,
      y: yBelow,
      type: "scatter",
      mode: "lines",
      name: "Cold",
      line: { color: "#206095", width: 6 },
    };
    heatLine = {
      x: xAbove,
      y: yAbove,
      type: "scatter",
      mode: "lines",
      name: "Heat",
      line: { color: "#d0021b", width: 6 },
    };
  }

  // Confidence Intervals
  const upperLine = {
    x: xAll,
    y: yLower,
    line: { color: "#fbc900", width: 0 },
    mode: "lines",
    name: "Lower bound",
    type: "scatter",
    showlegend: false,
    legendgroup: "Confidence Interval",
    marker: {
      symbol: "square",
    },
  };

  const lowerLine = {
    x: xAll,
    y: yUpper,
    fill: "tonexty",
    fillcolor: ciFill,
    line: { color: "#0f8243", width: 0 },
    mode: "lines",
    name: "Upper bound",
    type: "scatter",
    showlegend: false,
    legendgroup: "Confidence Interval",
    marker: {
      symbol: "square",
    },
  };

  // Plot MMT Line
  let mmtLine = {};
  if (plotMMT) {
    mmtLine = {
      x: [MinMortalityTemp, MinMortalityTemp],
      y: [0.95 * Math.min(...data.lower), 1.05 * Math.max(...data.upper)],
      line: { color: "#fbc900", width: 0 },
      mode: "lines",
      name: "Minimum Mortality Temperature",
      type: "scatter",
      showlegend: true,
      line: {
        width: 3,
        dash: "dot",
      },
    };
  }

  // Create Shared Legend Item
  const legendGroupTrace = {
    x: [null], // Dummy data
    y: [null], // Dummy data
    mode: "lines",
    name: "Confidence Interval", // Name representing the legend group
    type: "scatter",
    showlegend: true, // Show this trace in the legend
    legendgroup: "Confidence Interval",
    marker: {
      symbol: "square",
      color: "rgba(31, 146, 130, 0.3)",
    },
  };

  // Calculate OTR annotation location
  let OTRMidpoint = optimalLower + (optimalHigher - optimalLower) / 2;
  OTRX = optimalHigher;
  OTRXAnchor = "right";
  if (OTRMidpoint <= MinMortalityTemp) {
    OTRX = optimalLower;
    OTRXAnchor = "left";
  }

  // Plot OTR
  let otrAnno = [];
  let otrShapes = [];

  if (plotOTR) {
    otrAnno = [
      {
        x: OTRX,
        y: 1,
        xref: "x",
        yref: "paper",
        text: `Optimal temperature range: <br>${optimalLower} to ${optimalHigher}°C`,
        showarrow: false,
        xanchor: OTRXAnchor,
        size: 8,
        //bgcolor: 'white'
      },
    ];
    otrShapes = [
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: optimalLower,
        y0: 0,
        x1: optimalHigher,
        y1: 1,
        fillcolor: "#d3d3d3",
        opacity: 0.35,
        line: {
          width: 0,
        },
      },
      {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: optimalLower,
        y0: 0,
        x1: optimalLower,
        y1: 1,
        line: {
          width: 0,
          dash: "dash",
        },
      },
      {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: optimalHigher,
        y0: 0,
        x1: optimalHigher,
        y1: 1,
        line: {
          width: 0,
          dash: "dash",
        },
      },
    ];
  }

  const layout = {
    responsive: true,
    annotations: [...otrAnno],
    shapes: [...otrShapes],
    title: `Temperature related relative mortality risk for ${selectedGroup} using data from ${firstYear} to ${selectedYear}`,
    word_wrap: "break-word",
    paper_bgcolor: "rbga(255,255,255,1)",
    plot_bgcolor: "rbga(255,255,255,1)",
    xaxis: {
      title: {
        // Set the x-axis title
        text: "Temperature (°C)",
        standoff: 70,
      },
      showgrid: false, // Show x-axis grid lines
      zeroline: false, // Show x-axis zero line
      ticks: "outside",
      automargin: true,
    },
    yaxis: {
      title: { text: "Relative risk of mortality" }, // Set the y-axis title
      showgrid: true, // Show y-axis grid lines
      zeroline: false, // Show y-axis zero line
      range: [0.95 * Math.min(...data.lower), 1.05 * Math.max(...data.upper)],
    },
    font: {
      family: "Arial, sans-serif",
      size: 18,
      color: "black",
    },
    legend: {
      x: 0,
      y: 1,
      xanchor: "left",
      yanchor: "bottom",
      orientation: "h",
    },
  };

  // Remove OTR visual
  if (typeof optimalLower === "undefined") {
    layout.annotations = [];
    layout.shapes = [];
  }

  var config = { responsive: false };
  Plotly.newPlot(
    "plotlyLine",
    [mainLine, coldLine, heatLine, upperLine, lowerLine, legendGroupTrace, mmtLine],
    layout,
    config,
  );
}

// Plot line chart for Mental Health based on dropdown selection
function plotLineMH(divId) {
  const dropdown = document.getElementById("t7groupDropdown");
  if (!dropdown) {
    console.warn("Missing dropdown #t7groupDropdown");
    return;
  }

  const raw = (dropdown.value ?? "").trim();
  const hasValidSelection = raw && groupedDataLineGlobal?.[raw];

  const fallbackGroup = groupedDataLineGlobal
    ? Object.keys(groupedDataLineGlobal).find((k) => groupedDataLineGlobal?.[k])
    : null;

  const selectedGroup = hasValidSelection ? raw : fallbackGroup;

  if (!selectedGroup) {
    console.warn("No groups available in groupedDataLineGlobal");
    Plotly.purge(divId);
    return;
  }

  const data = groupedDataLineGlobal[selectedGroup];

  if (!data || !Array.isArray(data.temperature) || data.temperature.length === 0) {
    console.warn("No data for group:", selectedGroup);
    Plotly.purge(divId);
    return;
  }

  const x = data.temperature;
  const y = data.relativeRisk;
  const yLower = data.lower;
  const yUpper = data.upper;

  const traceLower = {
    x,
    y: yLower,
    type: "scatter",
    mode: "lines",
    line: { width: 0, shape: "spline", smoothing: 1.3 },
    hoverinfo: "skip",
    showlegend: false,
  };

  const traceUpper = {
    x,
    y: yUpper,
    type: "scatter",
    mode: "lines",
    line: { width: 0, shape: "spline", smoothing: 1.3 },
    fill: "tonexty",
    fillcolor: "rgba(42, 105, 145, 0.2)",
    hoverinfo: "skip",
    showlegend: false,
  };

  const traceCurve = {
    x,
    y,
    type: "scatter",
    mode: "lines",
    name: "Curve",
    line: { width: 2, shape: "spline", smoothing: 1.3, color: "#0A2E4D" },
    showlegend: false,
  };

  const layout = {
    margin: { l: 60, r: 20, t: 30, b: 50 },
    xaxis: { title: { text: "Temperature (°C)" } },
    yaxis: { title: { text: "RR" } },
    paper_bgcolor: "rgba(255,255,255,1)",
    plot_bgcolor: "rgba(255,255,255,1)",
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
    margin: { l: 60, r: 20, t: 60, b: 60 },
  };

  // Band first, curve last (so curve stays visible on top)
  Plotly.newPlot(divId, [traceLower, traceUpper, traceCurve], layout, { responsive: true });
  schedulePlotResize(divId);
}

// Plot scatter chart for mental health
function plotScatterMH(divId) {
  const dropdown = document.getElementById("t7groupDropdown");
  const availableGroups = Object.keys(groupedDataARYRGlobal || {});
  if (!availableGroups.length) {
    console.warn("Mental health ARYR data unavailable.");
    return;
  }

  const selectedGroup =
    dropdown && groupedDataARYRGlobal[dropdown.value] ? dropdown.value : availableGroups[0];
  if (dropdown && dropdown.value !== selectedGroup) {
    dropdown.value = selectedGroup;
  }

  const data = groupedDataARYRGlobal[selectedGroup];
  const rows = Array.isArray(data) ? data : [];

  const sorted = rows
    .map((d) => ({
      year: Number(d.year),
      ar: Number(d.ar),
      lower: Number(d.ar_lower_ci),
      upper: Number(d.ar_upper_ci),
    }))
    .filter((d) => Number.isFinite(d.year))
    .sort((a, b) => a.year - b.year);

  const years = sorted.map((d) => d.year);
  if (!years.length) {
    console.warn("Mental health ARYR data missing years.");
    return;
  }

  const middle = sorted.map((d) => d.ar);
  const lower = sorted.map((d) => d.lower);
  const upper = sorted.map((d) => d.upper);

  if (!divId) {
    console.warn(`${divId} element not found in DOM.`);
    return;
  }

  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const startTick = Math.ceil(minYear / 5) * 5;
  const tickvals = [];
  for (let y = startTick; y <= maxYear; y += 5) {
    tickvals.push(y);
  }

  const middleTrace = {
    x: years,
    y: middle,
    type: "scatter",
    mode: "lines",
    name: "AR",
    line: { color: "#0A2E4D", width: 2 },
  };

  const lowerTrace = {
    x: years,
    y: lower,
    type: "scatter",
    mode: "lines",
    name: "Lower",
    line: { color: "#2a6991", width: 1 },
  };

  const upperTrace = {
    x: years,
    y: upper,
    type: "scatter",
    mode: "lines",
    name: "Upper",
    line: { color: "#2a6991", width: 1 },
    fill: "tonexty",
    fillcolor: "rgba(42, 105, 145, 0.2)",
  };

  const layout = {
    xaxis: {
      title: { text: "Year" },
      tickmode: "array",
      tickvals,
      showgrid: true,
      zeroline: false,
    },
    yaxis: {
      title: { text: "AR (per 100,000 population)", standoff: 30 },
      automargin: true,
      showgrid: true,
      zeroline: false,
    },
    autosize: true,
    paper_bgcolor: "rgba(255,255,255,1)",
    plot_bgcolor: "rgba(255,255,255,1)",
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
    margin: { l: 60, r: 20, t: 60, b: 60 },
    showlegend: false,
  };

  Plotly.newPlot(divId, [lowerTrace, upperTrace, middleTrace], layout, { responsive: true });
  schedulePlotResize(divId);
}

// Plot bar chart for mental health
function plotBarMHARPM(divId, region) {
  const MONTH_TICKVALS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  const MONTH_TICKTEXT = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

  const regions = Object.keys(groupedDataARPMGlobal || {});
  if (!regions.length) {
    console.warn("plotBarMHARPM: groupedBarData is empty");
    return;
  }

  const resolvedRegion = region && groupedDataARPMGlobal[region] ? region : regions[0];
  const seriesRaw = groupedDataARPMGlobal[resolvedRegion];

  const rows = Array.isArray(seriesRaw) ? seriesRaw : [];
  if (!rows.length) {
    console.warn(`No data found for region: ${resolvedRegion}`);
    return;
  }

  const sorted = rows
    .map((d) => {
      const monthName = String(d.month ?? "");
      const order = MONTH_TICKVALS.indexOf(monthName);
      return {
        month: monthName,
        order: order === -1 ? 999 : order,
        ar: Number(d.ar),
        temp: Number(d.temp),
      };
    })
    .sort((a, b) => a.order - b.order);

  // Arrays for plotting
  const monthsSorted = sorted.map((d) => d.month);
  const arSorted = sorted.map((d) => d.ar);
  const tempSorted = sorted.map((d) => d.temp);

  // Bars: AR Deaths per 100,000 (left y-axis)
  const traceAR = {
    x: monthsSorted,
    y: arSorted,
    type: "bar",
    name: "AR",
    marker: { color: "#0A2E4D" },
    yaxis: "y",
  };

  // Line: Mean Temp (right y-axis)
  const traceTemp = {
    x: monthsSorted,
    y: tempSorted,
    type: "scatter",
    mode: "lines+markers",
    name: "Mean Temp (°C)",
    line: { color: "#2a6991", width: 2 },
    marker: { color: "#2a6991" },
    yaxis: "y2",
  };

  const layout = {
    barmode: "group",
    xaxis: {
      title: { text: "Month", standoff: 30 },
      automargin: true,
      type: "category",
      categoryorder: "array",
      tickvals: MONTH_TICKVALS,
      ticktext: MONTH_TICKTEXT,
    },
    yaxis: {
      title: { text: "AR (per 100,000 population)" },
    },
    yaxis2: {
      title: { text: "Mean Temp (°C)" },
      overlaying: "y",
      side: "right",
      showgrid: false,
      title: { text: "Mean Temp (°C)", standoff: 20 },
      automargin: true,
    },
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
    autosize: true,
    legend: { x: 0.4, y: 1.4 },
    margin: { l: 60, r: 70, t: 60, b: 60 },
  };

  Plotly.newPlot(divId, [traceAR, traceTemp], layout, { responsive: true });
  schedulePlotResize(divId);
}

// Plot line chart for Vector borne diseases
function plotCurveVB(selectedGroup) {
  const dropdown = document.getElementById("t5groupDropdown");
  dropdown.value = selectedGroup;
  if (!vectorborneCurveData || Object.keys(vectorborneCurveData).length === 0) {
    console.warn("Vectorborne curve data is unavailable.");
    return;
  }

  if (!vectorborneGroups.length) {
    vectorborneGroups = Object.keys(vectorborneCurveData);
  }

  if (dropdown && dropdown.options.length !== vectorborneGroups.length) {
    dropdown.innerHTML = "";
    vectorborneGroups.forEach((group) => {
      const option = document.createElement("option");
      option.value = group;
      option.textContent = group;
      dropdown.appendChild(option);
    });
    dropdown.addEventListener("change", (e) => plotCurveVB(e.target.value));
  }

  const groupKey =
    selectedGroup && vectorborneCurveData[selectedGroup] ? selectedGroup : vectorborneGroups[0];
  if (dropdown && dropdown.value !== groupKey) {
    dropdown.value = groupKey;
  }

  const traces = vectorborneCurveData[groupKey];
  if (!traces) {
    console.warn(`Vectorborne curve data missing for group: ${groupKey}`);
    return;
  }

  const targetEl = document.getElementById("vectorCurveDiv");
  if (!targetEl) {
    console.warn("vectorCurveDiv element not found in DOM.");
    return;
  }

  const baseTrace = {
    ...traces.mid,
    line: { color: "#C75E70", width: 4 },
    name: `${groupKey} relative risk`,
    mode: traces.mid.mode || "lines",
    type: traces.mid.type || "scatter",
  };

  const lowerTrace = {
    ...traces.low,
    line: { width: 0 },
    mode: traces.low.mode || "lines",
    type: traces.low.type || "scatter",
    showlegend: false,
    hoverinfo: "skip",
  };

  const upperTrace = {
    ...traces.high,
    fill: "tonexty",
    fillcolor: "rgba(248, 91, 91, 0.25)",
    line: { width: 0 },
    mode: traces.high.mode || "lines",
    type: traces.high.type || "scatter",
    showlegend: false,
    hoverinfo: "skip",
  };

  const xValues = baseTrace.x || [];
  const layout = {
    title: `${groupKey} (All Years Combined)`,
    paper_bgcolor: "rgba(255,255,255,1)",
    plot_bgcolor: "rgba(255,255,255,1)",
    shapes: [
      {
        type: "line",
        x0: Math.min(...xValues),
        y0: 1,
        x1: Math.max(...xValues),
        y1: 1,
        line: { color: "black", width: 2, dash: "dash" },
      },
    ],
    xaxis: {
      title: { text: "Rainfall" },
      showgrid: true,
      zeroline: true,
    },
    yaxis: {
      title: { text: "Relative Risk" },
      showgrid: true,
      zeroline: true,
    },
    font: { family: "OpenSans, Helvetica Neue, arial, sans-serif", size: 16, color: "black" },
    legend: { x: 0, y: 1 },
    margin: { l: 60, r: 30, t: 60, b: 60 },
  };

  Plotly.newPlot(targetEl, [lowerTrace, upperTrace, baseTrace], layout, { responsive: true });
  schedulePlotResize(targetEl);
}

// Plot bar chart for Vector borne diseases
function plotBarVB() {
  if (!vectorborneBarData || !vectorborneBarData.length) {
    console.warn("Vectorborne bar data unavailable.");
    return;
  }

  const targetEl = document.getElementById("vectorBarDiv");
  if (!targetEl) {
    console.warn("vectorBarDiv element not found in DOM.");
    return;
  }

  const regions = vectorborneBarData.map((item) => item.region);
  const values = vectorborneBarData.map((item) => item.AR_per_100k);

  const trace = {
    type: "bar",
    x: regions,
    y: values,
    marker: { color: "#0A2E4D" },
    text: values.map((v) => v.toFixed(2)),
    textposition: "inside",
    textfont: { color: "#ffffffff", size: 12 },
  };

  const layout = {
    title: "Attributable malaria rate per 100k (2024)",
    xaxis: { title: { text: "Region" }, tickangle: -45 },
    yaxis: { title: { text: "Attributable rate" } },
    paper_bgcolor: "rgba(255,255,255,1)",
    plot_bgcolor: "rgba(255,255,255,1)",
    font: { family: "OpenSans, Helvetica Neue, arial, sans-serif", size: 16, color: "black" },
    margin: { l: 60, r: 30, t: 80, b: 120 },
  };

  Plotly.newPlot(targetEl, [trace], layout, { responsive: true });
  schedulePlotResize(targetEl);
}

// Plot scatter chart for Vector borne diseases
function plotScatterVB() {
  if (!vectorborneScatterData || !vectorborneScatterData.length) {
    console.warn("Vectorborne scatter data unavailable.");
    return;
  }

  const targetEl = document.getElementById("vectorScatterDiv");
  if (!targetEl) {
    console.warn("vectorScatterDiv element not found in DOM.");
    return;
  }

  const years = vectorborneScatterData.map((item) => item.year);
  const values = vectorborneScatterData.map((item) => item.AR_Number);

  const trace = {
    type: "scatter",
    mode: "lines+markers",
    x: years,
    y: values,
    line: { color: "#0A2E4D", width: 4 },
    marker: { color: "#0A2E4D", size: 8 },
  };

  const layout = {
    title: "Number of malaria cases attributable to Extreme Rainfall",
    xaxis: { title: { text: "Year", standoff: 20 }, tickmode: "linear" },
    yaxis: { title: { text: "Attributable number" } },
    paper_bgcolor: "rgba(255,255,255,1)",
    plot_bgcolor: "rgba(255,255,255,1)",
    font: { family: "OpenSans, Helvetica Neue, arial, sans-serif", size: 16, color: "black" },
    margin: { l: 60, r: 30, t: 80, b: 100 },
  };

  Plotly.newPlot(targetEl, [trace], layout, { responsive: true });
  schedulePlotResize(targetEl);
}

// Plot bar chart based on dropdown selection
function plotBar() {
  const selectedYear = document.getElementById("outputYear").value;
  // const selectedYear = new Date(dropdownDate.value).getFullYear();
  const outputYearText = selectedYear == "" ? "" : " in " + selectedYear;
  const outputYearGraph = selectedYear == "" ? "" : "(" + selectedYear + ")";

  const dropdown = document.getElementById("groupDropdown");
  const selectedGroup = dropdown.value;

  document.getElementById("output_year_bar").textContent = outputYearText;
  document.getElementById("output_region_bar").textContent = selectedGroup;
  const dataRegionRate = groupedDataBarGlobalRate[selectedGroup].region;
  const dataHighHeatRate = groupedDataBarGlobalRate[selectedGroup].highHeat;
  const dataHighHeatRateUpper = groupedDataBarGlobalRate[selectedGroup].highHeatUpper;
  const dataHighHeatRateLower = groupedDataBarGlobalRate[selectedGroup].highHeatLower;
  const dataHighColdRate = groupedDataBarGlobalRate[selectedGroup].highCold;
  const dataHighColdRateUpper = groupedDataBarGlobalRate[selectedGroup].highColdUpper;
  const dataHighColdRateLower = groupedDataBarGlobalRate[selectedGroup].highColdLower;

  const dataRegionDeaths = groupedDataBarGlobalDeaths[selectedGroup].region;
  const dataHighHeatDeaths = groupedDataBarGlobalDeaths[selectedGroup].highHeat;
  const dataHighHeatDeathsUpper = groupedDataBarGlobalDeaths[selectedGroup].highHeatUpper;
  const dataHighHeatDeathsLower = groupedDataBarGlobalDeaths[selectedGroup].highHeatLower;
  const dataHighColdDeaths = groupedDataBarGlobalDeaths[selectedGroup].highCold;
  const dataHighColdDeathsUpper = groupedDataBarGlobalDeaths[selectedGroup].highColdUpper;
  const dataHighColdDeathsLower = groupedDataBarGlobalDeaths[selectedGroup].highColdLower;

  let coldCIRate = dataHighColdRateUpper.map((i) => i - dataHighColdRateLower);
  let heatCIRate = dataHighHeatRateUpper.map((i) => i - dataHighHeatRateLower);

  let coldCIDeaths = dataHighColdDeathsUpper.map((i) => i - dataHighColdDeathsLower);
  let heatCIDeaths = dataHighHeatDeathsUpper.map((i) => i - dataHighHeatDeathsLower);

  const heatBarRate = {
    x: dataRegionRate,
    y: dataHighHeatRate,
    name: "High Heat",
    type: "bar",
    marker: { color: "#d0021b" },
    error_y: {
      type: "data",
      array: heatCIRate,
      visible: true,
    },
  };

  const coldBarRate = {
    x: dataRegionRate,
    y: dataHighColdRate,
    name: "High Cold",
    type: "bar",
    marker: { color: "#206095" },
    error_y: {
      type: "data",
      array: coldCIRate,
      visible: true,
    },
  };

  const layoutRate = {
    title: `Attributable mortality/100k in ${selectedGroup} ${outputYearGraph}`,
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
    paper_bgcolor: "rbga(255,255,255,1)",
    plot_bgcolor: "rbga(255,255,255,1)",
    barmode: "group",
    xaxis: {
      title: { text: "Geography" },
    },
    yaxis: {
      title: { text: "Attr. mort./100k" },
    },
  };

  const heatBarDeaths = {
    x: dataRegionDeaths,
    y: dataHighHeatDeaths,
    name: "High Heat",
    type: "bar",
    marker: { color: "#d0021b" },
    error_y: {
      type: "data",
      array: heatCIDeaths,
      visible: true,
    },
  };

  const coldBarDeaths = {
    x: dataRegionDeaths,
    y: dataHighColdDeaths,
    name: "High Cold",
    type: "bar",
    marker: { color: "#206095" },
    error_y: {
      type: "data",
      array: coldCIDeaths,
      visible: true,
    },
  };

  const layoutDeaths = {
    title: `Number of deaths attributable to high-intensity heat and cold for ${selectedGroup} ${outputYearGraph}`,
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
    paper_bgcolor: "rbga(255,255,255,1)",
    plot_bgcolor: "rbga(255,255,255,1)",
    barmode: "group",
    xaxis: {
      title: { text: "Geography" },
    },
    yaxis: {
      title: { text: "Temperature attributable deaths" },
    },
  };

  var config = { responsive: true };

  Plotly.newPlot("plotlyBarRate", [heatBarRate, coldBarRate], layoutRate, config);
  Plotly.newPlot("plotlyBarDeaths", [heatBarDeaths, coldBarDeaths], layoutDeaths);
}

// Plot data table based on dropdown selection
function plotTable() {
  const dropdown = document.getElementById("groupDropdown");
  const selectedGroup = dropdown.value;

  const dataX = groupedDataLineGlobal[selectedGroup].temperature;
  const dataY = groupedDataLineGlobal[selectedGroup].relativeRisk;

  const tableData = [
    {
      type: "table",
      header: {
        values: [["temperature"], ["relativeRisk"]],
        align: "center",
        height: 35,
        line: { width: 1, color: "black" },
        fill: { color: "gray" },
        font: { family: "Arial", size: 20, color: "white" },
      },
      cells: {
        values: [dataX, dataY],
        align: "center",
        height: 35,
        line: { color: "black", width: 1 },
        fill: { color: ["white"] },
        font: { family: "Arial", size: 20, color: "black" },
      },
    },
  ];

  const layout = {
    title: "Data Table",
  };

  var config = { responsive: true };

  Plotly.newPlot("plotlyTable", tableData, layout, config);
}

function plotWildfiresRR(divId) {
  const dropdown = document.getElementById("t2groupDropdown");
  const selectedRegionData = groupedDataLineGlobal[dropdown.value];

  let x_values = ["0 days"];
  let x_ticks = [0];

  for (let i = 1; i <= selectedRegionData.lag.length; i++) {
    x_values.push("0-" + i + " days");
    x_ticks.push(i);
  }

  let wfRRLower = selectedRegionData.relativeRisk.map(
    (num, i) => num - selectedRegionData.lower[i],
  );
  let wfRRUpper = selectedRegionData.relativeRisk.map(
    (num, i) => selectedRegionData.upper[i] - num,
  );

  const mainPlot = {
    type: "scatter",
    mode: "markers",
    x: x_values,
    y: selectedRegionData.relativeRisk,
    error_y: {
      type: "data",
      symmetric: false,
      width: 4,
      thickness: 2,
      array: wfRRUpper,
      arrayminus: wfRRLower,
      visible: true,
    },
    name: "Relative risk",
    line: { color: "#0A2E4D", width: 4 },
    marker: { color: "#0A2E4D", size: 8 },
  };

  const layout = {
    title: {
      text: "Associations between risk of all cause<br>mortality and wildfire smoke (PM2.5)",
      standoff: 70,
    },
    xaxis: {
      title: { text: "Lag", standoff: 20 },
      tickvals: x_ticks,
      ticktext: x_values,
      tickmode: "array",
    },
    yaxis: {
      title: { text: "Relative Risk", standoff: 20 },
    },
    paper_bgcolor: "rgba(255,255,255,1)",
    plot_bgcolor: "rgba(255,255,255,1)",
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
    margin: { l: 60, r: 30, t: 80, b: 100 },
  };

  const config = { responsive: true };

  Plotly.newPlot(divId, [mainPlot], layout, config);
  schedulePlotResize(divId);
}

function plotWildfiresANAR(divId, region, metric = "AN") {
  const regions = Object.keys(groupedDataANAFGlobal || {});
  if (regions.length === 0) {
    console.warn("plotWildfiresANAR: groupedDataANAFGlobal is empty");
    return;
  }

  const resolvedRegion = region && groupedDataANAFGlobal[region] ? region : regions[0];

  const series = groupedDataANAFGlobal[resolvedRegion];
  if (!series) {
    console.warn(`No data found for region: ${region}`);
    return;
  }

  const years = series.year;
  const months = series.month || [];

  const x = years.map((year, idx) => {
    const month = months[idx] != null ? months[idx] : 1;
    return new Date(year, month - 1, 1); // JS months are 0–11
  });

  // Resolve metric (AN = number, AR = rate)
  let metricNorm = (metric || "AN").toUpperCase();
  if (metricNorm !== "AN" && metricNorm !== "AR") {
    console.warn(`Unknown metric "${metric}", defaulting to "AN"`);
    metricNorm = "AN";
  }

  let yLower, yMiddle, yUpper, yAxisTitle, metricLabel;

  if (metricNorm === "AN") {
    // Attributable Number
    yLower = series.lower_an;
    yMiddle = series.an;
    yUpper = series.upper_an;
    yAxisTitle = "Attributable deaths (number)";
    metricLabel = "Attributable number";
  } else {
    // Attributable Rate (per 100k)
    yLower = series.lower_rate;
    yMiddle = series.rate;
    yUpper = series.upper_rate;
    yAxisTitle = "Attributable rate";
    metricLabel = "Attributable rate";
  }

  const traceLower = {
    x,
    y: yLower,
    mode: "lines",
    name: "Lower",
    line: { color: "#2a6991", width: 1 },
  };

  const traceUpper = {
    x,
    y: yUpper,
    mode: "lines",
    name: "Upper",
    line: { color: "#2a6991", width: 1 },
    fill: "tonexty",
    fillcolor: "rgba(42, 105, 145, 0.2)",
  };

  const traceMiddle = {
    x,
    y: yMiddle,
    mode: "lines",
    name: "Middle",
    line: { color: "#0A2E4D", width: 2 },
  };

  const layout = {
    title: { text: `${metricLabel} over time – ${resolvedRegion}`, standoff: 70 },
    xaxis: {
      title: { text: "Year" },
      type: "date",
      tickformat: "%Y",
      dtick: "M12",
    },
    yaxis: {
      title: { text: yAxisTitle },
    },
    autosize: true,
    margin: { l: 60, r: 20, t: 60, b: 60 },
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
  };

  const config = {
    responsive: true,
  };

  Plotly.newPlot(divId, [traceLower, traceUpper, traceMiddle], layout, config);
  schedulePlotResize(divId);
}

function plotWildfiresARPM(divId, region) {
  // Fixed month order so the x-axis is always Jan -> Dec
  const MONTH_ORDER = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const regions = Object.keys(groupedDataARPMGlobal || {});
  if (regions.length === 0) {
    console.warn("plotWildfiresARPM: groupedBarData is empty");
    return;
  }
  const resolvedRegion = region && groupedDataARPMGlobal[region] ? region : regions[0];

  const series = groupedDataARPMGlobal[resolvedRegion];
  if (!series) {
    console.warn(`No data found for region: ${region}`);
    return;
  }

  // Sort data by MONTH_ORDER so x-axis is Jan..Dec
  const indices = series.months
    .map((m, i) => ({ m, i, order: MONTH_ORDER.indexOf(m) }))
    .sort((a, b) => a.order - b.order)
    .map((obj) => obj.i);

  const monthsSorted = indices.map((i) => series.months[i]);
  const deathsSorted = indices.map((i) => series.deathsPer100k[i]);
  const pmSorted = indices.map((i) => series.meanPm[i]);

  // Bars: Deaths per 100,000 (left y-axis)
  const traceDeaths = {
    x: monthsSorted,
    y: deathsSorted,
    type: "bar",
    name: "Deaths per 100,000",
    marker: {
      color: "#0A2E4D", // dark blue
    },
    yaxis: "y",
  };

  // Line: Mean PM2.5 (right y-axis)
  const tracePm = {
    x: monthsSorted,
    y: pmSorted,
    type: "scatter",
    mode: "lines+markers",
    name: "Mean PM2.5",
    line: {
      color: "#2a6991", // purple
      width: 2,
    },
    marker: {
      color: "#2a6991",
    },
    yaxis: "y2",
  };

  const data = [traceDeaths, tracePm];

  const layout = {
    title: {
      text: "Deaths per 100,000 population <br> attributable to wildfire-related PM2.5",
      standoff: 70,
    },
    barmode: "group",
    xaxis: {
      title: { text: "Month" },
      type: "category",
      categoryorder: "array",
      categoryarray: MONTH_ORDER,
    },
    yaxis: {
      title: { text: "Deaths per 100,000" },
    },
    yaxis2: {
      title: { text: "Mean PM2.5" },
      overlaying: "y",
      side: "right",
      showgrid: false,
    },
    font: {
      family: "OpenSans, Helvetica Neue, arial, sans-serif",
      size: 16,
      color: "black",
    },
    autosize: true,
    margin: { l: 60, r: 60, t: 60, b: 60 },
  };

  const config = {
    responsive: true,
  };

  Plotly.newPlot(divId, data, layout, config);
  schedulePlotResize(divId);
}

// Convert data to CSV
function convertObjectToCSV(jsonData) {
  let csvData = "";
  let headers = Object.keys(jsonData[0]).join(",") + "\n";
  csvData += headers;

  jsonData.forEach(function (row) {
    let values = Object.values(row).join(",");
    csvData += values + "\n";
  });

  return csvData;
}

// Download CSV
function downloadCSV(data, filename) {
  const csvFile = new Blob([data], { type: "text/csv" });
  const csvURL = window.URL.createObjectURL(csvFile);
  const tempLink = document.createElement("a");

  tempLink.href = csvURL;
  tempLink.setAttribute("download", filename);
  document.body.appendChild(tempLink);
  tempLink.click();
  document.body.removeChild(tempLink);
}

// Download ZIP
function downloadZIP(zip_path, save_fname) {
  return fetch("/get_zip_file", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ path: zip_path, fname: save_fname }),
  }).then((response) => {
    return response.blob();
  });
}

// preview data
function previewData(file, tableid, titleText) {
  Papa.parse(file, {
    complete: function (previewCSV) {
      const container = document.getElementById(tableid);
      container.innerHTML = "";

      const data = previewCSV.data || [];
      const subset = data.slice(0, 6);
      if (subset.length === 0) return;

      // Optional title
      if (titleText) {
        const title = document.createElement("p");
        title.classList.add("ons-u-fs-r--b");
        title.textContent = titleText;
        container.appendChild(title);
      }
      var table = document.createElement("table");
      table.className = "ons-table";

      // --- THEAD from first row ---
      var thead = document.createElement("thead");
      thead.className = "ons-table__head";
      var headRow = document.createElement("tr");
      headRow.className = "ons-table__row";

      subset[0].forEach(function (cellData) {
        var th = document.createElement("th");
        th.className = "ons-table__header";
        th.setAttribute("scope", "col");
        th.appendChild(document.createTextNode(cellData));
        headRow.appendChild(th);
      });

      thead.appendChild(headRow);
      table.appendChild(thead);

      // --- TBODY from remaining rows ---
      var tableBody = document.createElement("tbody");
      tableBody.className = "ons-table__body";

      subset.slice(1).forEach(function (rowData) {
        var row = document.createElement("tr");
        row.className = "ons-table__row";

        rowData.forEach(function (cellData) {
          var cell = document.createElement("td");
          cell.className = "ons-table__cell";
          cell.appendChild(document.createTextNode(cellData));
          row.appendChild(cell);
        });

        tableBody.appendChild(row);
      });

      table.appendChild(tableBody);
      container.appendChild(table);
    },
  });
}

check_file = function (file, ext, max_size) {
  var found_ext = file.value.match(/\.([^\.]+)$/)[1];
  if (found_ext != ext) {
    alert(`Please upload a ${ext} file.`);
    file.value = "";
    return false;
  }
  // convert max_size (MB) to bytes
  max_size_bytes = 1048576 * max_size;
  if (file.files[0].size > max_size_bytes) {
    alert("File upload can not exceed " + max_size + "MB");
    return false;
  }
  return true;
};

let csvFile = null; // This variable will hold the file

on("csvInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateDropdownWithCSV(csvFile);
  populateDropdownWithGJSON("countryCol");
  document.getElementById("tableTitle").style.display = "block";
  document.getElementById("tableDiv").style.display = "block";
  previewData(e.target.files[0], "previewTable");
});

on("t0csvInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  t0populateDropdownWithCSV(csvFile);
  document.getElementById("t0tableTitle").style.display = "block";
  document.getElementById("t0tableDiv").style.display = "block";
  previewData(e.target.files[0], "t0previewTable");
});

on("t2csvInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateT2DropdownWithCSV(csvFile);
  previewData(e.target.files[0], "t2previewTable");
});

on("t7csvInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateT7DropdownWithCSV(csvFile);
  previewData(e.target.files[0], "t7previewTable");
});

on("t8csvInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateT8DropdownWithCSV(csvFile);
  previewData(e.target.files[0], "t8previewTable");
});

// T4 (diarrhea) table previews
on("t4healthInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateT4HealthDropdownWithCSV(csvFile);
  document.getElementById("t4htableTitle").style.display = "block";
  document.getElementById("t4htableDiv").style.display = "block";
  previewData(e.target.files[0], "t4hpreviewTable");
});

on("t4climateInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateT4ClimateDropdownWithCSV(csvFile);
  document.getElementById("t4ctableTitle").style.display = "block";
  document.getElementById("t4ctableDiv").style.display = "block";
  previewData(e.target.files[0], "t4cpreviewTable");
});

on("t4sfInput", "change", function (e) {
  if (check_file(e.target, "zip", 150) == false) return;
});

// T5 (Malaria) table previews
on("t5healthInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateT5HealthDropdownWithCSV(csvFile);
  // previewData(e.target.files[0], "t5hpreviewTable", "Uploaded health data preview");
});

on("t5climateInput", "change", function (e) {
  if (check_file(e.target, "csv", 40) == false) return;
  csvFile = e.target.files[0];
  populateT5ClimateDropdownWithCSV(csvFile);
  // previewData(e.target.files[0], "t5cpreviewTable", "Uploaded climate data preview");
});

on("t5sfInput", "change", function (e) {
  if (check_file(e.target, "zip", 150) == false) return;
});

// Download data when button clicked (RR for H+C)
on("downloadButtonRR", "click", function () {
  const csvRR = convertObjectToCSV(RRResponse);

  downloadCSV(csvRR, "relative_risk_regions.csv");
});

// Download data when button clicked (AD for H+C)
on("downloadButtonRate", "click", function () {
  const csvRate = convertObjectToCSV(RateResponse);

  downloadCSV(csvRate, "attributable_deaths_regions.csv");
});

// Download data when button clicked (AN for H+C)
on("downloadButtonDeaths", "click", function () {
  const csvDeaths = convertObjectToCSV(DeathsResponse);

  downloadCSV(csvDeaths, "attributable_numbers_regions.csv");
});

function createZipDownload(blob, fname) {
  const zipURL = window.URL.createObjectURL(blob);
  const tempLink = document.createElement("a");

  tempLink.href = zipURL;
  tempLink.setAttribute("download", fname);
  document.body.appendChild(tempLink);
  tempLink.click();
  document.body.removeChild(tempLink);
}

// Downloads for wildfire (t2)
on("downloadWildfiresRR", "click", function () {
  const csvWildfiresRR = convertObjectToCSV(RRResponse);
  downloadCSV(csvWildfiresRR, "wildfires_relative_risk.csv");
});

// Download data when button clicked
on("downloadWildfiresANAF", "click", function () {
  const csvWildfiresANAF = convertObjectToCSV(RateResponse);
  downloadCSV(csvWildfiresANAF, "wildfires_AN_AF.csv");
});

// Disable AN/AF download when region based analysis=False
const regionRadios = document.querySelectorAll('input[name="t2-results-by-region"]');
const downloadBtn = getEl("downloadWildfiresANAF");
const yesRegionRadio = getEl("t2-results-by-region-1");
const graphElems = ["wildfiresAnPlot", "wildfiresAnDesc", "wildfiresAfPlot", "wildfiresAfDesc"];

function updateRegionUI() {
  if (!downloadBtn || !yesRegionRadio) return;

  // "Yes" radio
  const yesSelected = yesRegionRadio.checked;

  // Enable/disable button
  downloadBtn.disabled = !yesSelected;

  // Show/hide graphs
  graphElems.forEach((id) => {
    const el = getEl(id);
    if (el) el.hidden = !yesSelected;
  });
}

// Listen to changes on both radios
regionRadios.forEach((radio) => {
  radio.addEventListener("change", updateRegionUI);
});

if (regionRadios.length && downloadBtn && yesRegionRadio) {
  updateRegionUI();
}

let RRResponse = null;
let RateResponse = null;
let DeathsResponse = null;
let WildfiresResponse = null;
let DescStatsPath = null;
let DescStatsFname = null;

// Download data when button clicked
let DiarrheaBlob = null;
on("t4downloadButton", "click", function () {
  if (!DiarrheaBlob) {
    downloadZIP(DiarrheaZipPath, DiarrheaZipFname).then((blob) => {
      DiarrheaBlob = blob;
      createZipDownload(DiarrheaBlob, DiarrheaZipFname);
    });
  } else {
    createZipDownload(DiarrheaBlob, DiarrheaZipFname);
  }
});

// Download data when button clicked
let MalariaBlob = null;
on("t5downloadButton", "click", function () {
  if (!MalariaBlob) {
    downloadZIP(MalariaZipPath, MalariaZipFname).then((blob) => {
      MalariaBlob = blob;
      createZipDownload(MalariaBlob, MalariaZipFname);
    });
  } else {
    createZipDownload(MalariaBlob, MalariaZipFname);
  }
});

// Download data when button clicked
let DescStatsBlob = null;
on("t0downloadButton", "click", function () {
  if (!DescStatsBlob) {
    downloadZIP(DescStatsPath, DescStatsFname).then((blob) => {
      DescStatsBlob = blob;
      createZipDownload(DescStatsBlob, DescStatsFname);
    });
  } else {
    createZipDownload(DescStatsBlob, DescStatsFname);
  }
});

on("t7downloadButtonRR", "click", function () {
  if (!RRResponse) {
    return;
  }
  const csvMentalHealthRR = convertObjectToCSV(RRResponse);
  downloadCSV(csvMentalHealthRR, "mental_health_relative_risk.csv");
});

// Upload data when button clicked, access API and plot results
on("uploadBtn", "click", async function (e) {
  e.preventDefault();

  const file = document.getElementById("csvInput").files[0];
  const deaths = document.getElementById("deathsCol").value;
  const time = document.getElementById("t1dateCol").value;
  const temp = document.getElementById("tempCol").value;
  const pop = document.getElementById("popCol").value;
  const country = document.getElementById("countryCol").value;
  const subgeo = document.getElementById("subgeoCol").value;
  const ind1 = document.getElementById("ind1Col").value;
  const ind2 = document.getElementById("ind2Col").value;
  const ind3 = document.getElementById("ind3Col").value;
  const ind4 = document.getElementById("ind4Col").value;
  // const disagg = document.getElementById("disaggCheck").checked;
  const meta = document.getElementById("metaCheck").checked;
  const rr_dist = document.getElementById("rrDistLength").value;
  const output_year = document.getElementById("outputYear").value;
  const lag = document.getElementById("lag").value;
  const seasonal = document.getElementById("seasonal").value;

  if (!file) {
    alert("Please select a CSV file first.");
    return;
  }
  if (!deaths) {
    alert("Please select a deaths column");
    return;
  }
  if (!temp) {
    alert("Please select a temperature column");
    return;
  }
  if (!pop) {
    alert("Please select a population column");
    return;
  }
  // if (!country) {
  //   alert("Please select a country");
  //   return;
  // }
  // if (!subgeo) {
  //   alert("Please select a sub-geography column");
  //   return;
  // }

  document.querySelector(".spinner").style.visibility = "visible";
  document.getElementById("apiMessage").innerHTML = "Sending data";

  let formFile = new FormData();
  formFile.append("file", file);
  formFile.append("deaths", deaths);
  formFile.append("time", time);
  formFile.append("temp", temp);
  formFile.append("pop", pop);
  formFile.append("country", country);
  formFile.append("subgeo", subgeo);
  formFile.append("ind1", ind1);
  formFile.append("ind2", ind2);
  formFile.append("ind3", ind3);
  formFile.append("ind4", ind4);
  // formFile.append("disagg", disagg);
  formFile.append("meta", meta);
  formFile.append("rr_dist", rr_dist);
  formFile.append("output_year", output_year);
  formFile.append("lag", lag);
  formFile.append("seasonal", seasonal);

  fetch("/heat_and_cold_indicator", {
    method: "POST",
    body: formFile,
  })
    .then((response) => {
      if (!response.ok) {
        document.querySelector(".spinner").style.visibility = "hidden";
        document.getElementById("apiMessage").innerHTML =
          '<p class="text-lg text-red-400">Processing Error</p>';
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      responseData = data.json_response;
      responseShp = data.joined_gdf;

      getRelRiskAPIOutput(responseData[0], "regions");
      getAttrRateAPIOutput(responseData[4]);
      getAttrDeathsAPIOutput(responseData[2]);
      populateDropdownWithRegion(groupedDataLineGlobal, "groupDropdown");
      document.getElementById("HeatAndColdViewResultsTab").click();

      // plotAPIOnMap(responseShp);

      RRResponse = responseData[0];
      RateResponse = responseData[4];
      DeathsResponse = responseData[2];

      document.querySelector(".spinner").style.visibility = "hidden";
      document.getElementById("apiMessage").innerHTML = "";
      document.getElementById("heatAndColdResultsPlot").style.visibility = "visible";
      // document.getElementById("graph-text-map").style.visibility = "visible";
      // document.getElementById("graph-text-plot").style.visibility = "visible";
      // document.getElementById("graph-text-bar").style.visibility = "visible";

      // Select the first region in the dropdown
      // Step 1: Select the <select> element
      const selectElement = document.getElementById("groupDropdown");

      // Step 2: Access the first <option> element
      const firstOption = selectElement.options[0];

      // Step 3: Trigger a click event on the first <option> element
      firstOption.selected = true; // Select the first option
      selectElement.dispatchEvent(new Event("change")); // Trigger the change

      // Display the year value in the maps description
      document.getElementById("output_year_map").textContent = output_year;
    })
    .catch((error) => {
      console.error("Error fetching data from the api:", error);
    });
});

// Upload data when button clicked, access API and plot results
on("t2Analyse", "click", async function (e) {
  e.preventDefault();
  const ERROR_TARGET = "t2ApiError";

  const file = getFile("t2csvInput");

  const joinWildfireData = getValue("join_wildfire_data");
  const ncdfPath = getValue("ncdf_path");
  const shpPath = getValue("shp_path");
  const dateCol = getValue("date_col");
  const regionCol = getValue("region_col");
  const meanTempCol = getValue("mean_temperature_col");
  const healthOutcomeCol = getValue("health_outcome_col");
  const pm25Col = getValue("pm_25_col");

  const wildfireLag = getNumber("wildfire_lag");
  const temperatureLag = getNumber("temperature_lag");
  const splineTempDegFreedom = getNumber("spline_temperature_degrees_freedom");
  const scaleFactorWildfirePM = getNumber("scale_factor_wildfire_pm");

  const byRegion = getEl("t2-results-by-region-1")?.checked ?? false;

  if (!file) {
    showOnsError(ERROR_TARGET, "Please select a CSV file first.");
    return;
  }
  if (!dateCol) {
    showOnsError(ERROR_TARGET, "Please select a date column");
    return;
  }
  if (!meanTempCol) {
    showOnsError(ERROR_TARGET, "Please select a mean temperature column.");
    return;
  }
  if (!healthOutcomeCol) {
    showOnsError(ERROR_TARGET, "Please select a health outcome column");
    return;
  }
  if (!pm25Col) {
    showOnsError(ERROR_TARGET, "Please select a PM2.5 column");
    return;
  }
  if (!regionCol && byRegion) {
    showOnsError(ERROR_TARGET, "Please select a region column to do region based analysis");
    return;
  }
  const analyseBtn = getEl("t2Analyse");

  // Loading
  hideOnsError(ERROR_TARGET);
  analyseBtn.classList.add("ons-is-loading");

  let formFile = new FormData();
  formFile.append("file", file);
  formFile.append("join_wildfire_data", joinWildfireData);
  formFile.append("ncdf_path", ncdfPath);
  formFile.append("shp_path", shpPath);
  formFile.append("date_col", dateCol);
  formFile.append("region_col", regionCol);
  formFile.append("mean_temperature_col", meanTempCol);
  formFile.append("health_outcome_col", healthOutcomeCol);
  formFile.append("pm_25_col", pm25Col);
  formFile.append("wildfire_lag", wildfireLag);
  formFile.append("temperature_lag", temperatureLag);
  formFile.append("spline_temperature_degrees_freedom", splineTempDegFreedom);
  formFile.append("scale_factor_wildfire_pm", scaleFactorWildfirePM);
  formFile.append("relative_risk_by_region", byRegion);

  fetch("/wildfires", {
    method: "POST",
    body: formFile,
  })
    .then(async (response) => {
      if (!response.ok) {
        analyseBtn.classList.remove("ons-is-loading");
        const errorData = await parseErrorResponse(response);
        showOnsErrorEnhanced(ERROR_TARGET, errorData);
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      const { rr_results = [], an_af_results = [], ar_pm_results = [] } = data ?? {};

      // Set globals for plots & responses for download
      // groupedDataLineGlobal
      reformatWildfiresRR(rr_results);
      RRResponse = rr_results;

      if (byRegion) {
        // groupedDataANAFGlobal
        reformatWildfiresANAF(an_af_results);
        RateResponse = an_af_results;
        // groupedDataARPMGlobal
        reformatWildfiresARPM(ar_pm_results);
      }

      // Dropdown
      populateDropdownWithRegion(groupedDataLineGlobal, "t2groupDropdown");

      // Plot
      if (byRegion) {
        plotWildfiresANAR("wildfiresAnPlot", null, "AR");
        plotWildfiresARPM("wildfiresAfPlot");
      }
      plotWildfiresRR("wildfiresRRPlot");

      // Finished loading, switch to results tab
      analyseBtn.classList.remove("ons-is-loading");
      hideOnsError(ERROR_TARGET);
      getEl("wildfiresResults").style.visibility = "visible";
      getEl("tab_wildfires-view-results").click();
    })
    .catch((error) => {
      analyseBtn.classList.remove("ons-is-loading");
      // Only show generic error if not already shown by structured error handler
      if (!error.message.includes("HTTP error")) {
        showOnsErrorEnhanced(ERROR_TARGET, "Processing error. Please check your inputs.");
      }
      console.error("Error fetching data from the api:", error);
    });
});

// Upload data when button clicked, access API and plot results
on("t7Analyse", "click", async function (e) {
  e.preventDefault();
  const ERROR_TARGET = "t7ApiError";

  // csv upload
  const file = getFile("t7csvInput");

  // selects
  const t7timeCol = getValue("t7timeCol");
  const t7geographyCol = getValue("t7geographyCol");
  const t7tempCol = getValue("t7tempCol");
  const t7healthOutcomeCol = getValue("t7healthOutcomeCol");
  const t7popCol = getValue("t7popCol");

  // extra
  const t7country = getValue("t7country");
  const t7meta = getEl("t7-results-by-region-1")?.checked ?? false;

  // Dynamic checkboxes
  const t7independentCols = Array.from(
    document.querySelectorAll('#t7IndependentColList input[type="checkbox"]:checked'),
  ).map((cb) => cb.value);

  const t7controlCols = Array.from(
    document.querySelectorAll('#t7ControlColList input[type="checkbox"]:checked'),
  ).map((cb) => cb.value);

  if (!file) {
    showOnsError(ERROR_TARGET, "Please select a CSV file first.");
    return;
  }
  if (!t7timeCol) {
    showOnsError(ERROR_TARGET, "Please select a date column");
    return;
  }
  if (!t7tempCol) {
    showOnsError(ERROR_TARGET, "Please select a temperature column");
    return;
  }
  if (!t7healthOutcomeCol) {
    showOnsError(ERROR_TARGET, "Please select a health outcome column");
    return;
  }
  if (!t7popCol) {
    showOnsError(ERROR_TARGET, "Please select a population column");
    return;
  }
  if (!t7geographyCol) {
    showOnsError(ERROR_TARGET, "Please select a geography column");
    return;
  }
  const analyseBtn = getEl("t7Analyse");

  // Loading
  hideOnsError(ERROR_TARGET);
  analyseBtn.classList.add("ons-is-loading");

  let formFile = new FormData();
  formFile.append("file", file);
  formFile.append("date_col", t7timeCol);
  formFile.append("region_col", t7geographyCol);
  formFile.append("temperature_col", t7tempCol);
  formFile.append("health_outcome_col", t7healthOutcomeCol);
  formFile.append("population_col", t7popCol);
  formFile.append("independent_cols", t7independentCols);
  formFile.append("control_cols", t7controlCols);
  formFile.append("meta_analysis", t7meta);
  formFile.append("country", t7country);

  fetch("/mental_health", {
    method: "POST",
    body: formFile,
  })
    .then(async (response) => {
      if (!response.ok) {
        // Finished loading, error state
        analyseBtn.classList.remove("ons-is-loading");
        const errorData = await parseErrorResponse(response);
        showOnsErrorEnhanced(ERROR_TARGET, errorData);
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      const { rr_results = [], attr_mth_list = [], attr_yr_list = [] } = data ?? {};

      // Set globals for plots & responses for download
      // groupedDataLineGlobal
      getRelRiskAPIOutputMH(rr_results, "disagg");
      groupedDataARPMGlobal = attr_mth_list;
      groupedDataARYRGlobal = attr_yr_list;
      RRResponse = rr_results;

      // Dropdown
      populateDropdownWithRegion(groupedDataLineGlobal, "t7groupDropdown");

      // Plot
      plotLineMH("mentalHealthRRPlot");
      plotScatterMH("mentalHealthARYRPlot");
      plotBarMHARPM("mentalHealthARMPlot");

      // Finished loading, switch to results tab
      analyseBtn.classList.remove("ons-is-loading");
      hideOnsError(ERROR_TARGET);
      getEl("t7graph-text-plot").style.visibility = "visible";
      getEl("tab_mental-health-view-results").click();
    })
    .catch((error) => {
      analyseBtn.classList.remove("ons-is-loading");
      // Only show generic error if not already shown by structured error handler
      if (!error.message.includes("HTTP error")) {
        showOnsErrorEnhanced(ERROR_TARGET, "Processing error. Please check your inputs.");
      }
      console.error("Error fetching data from the api:", error);
    });
});

// Air pollution: submit form, call /airpollution, surface results.
let AirPollutionResponse = null;
on("t8Analyse", "click", async function (e) {
  e.preventDefault();
  const ERROR_TARGET = "t8ApiError";

  const file = getFile("t8csvInput");
  const dateCol = getValue("t8date_col");
  const regionCol = getValue("t8region_col");
  const pm25Col = getValue("t8pm25_col");
  const deathsCol = getValue("t8deaths_col");
  const populationCol = getValue("t8population_col");
  const humidityCol = getValue("t8humidity_col");
  const precipitationCol = getValue("t8precipitation_col");
  const tmaxCol = getValue("t8tmax_col");
  const windSpeedCol = getValue("t8wind_speed_col");

  const maxLag = getValue("t8max_lag");
  const dfSeasonal = getValue("t8df_seasonal");
  const movingAverageWindow = getValue("t8moving_average_window");
  const attrThr = getValue("t8attr_thr");
  const referenceStandards = getValue("t8reference_standards");
  const yearsFilter = getValue("t8years_filter");
  const regionsFilter = getValue("t8regions_filter");

  const includeNational = getEl("t8-include-national-1")?.checked ?? true;
  const runPower = getEl("t8-run-power-1")?.checked ?? false;

  if (!file) {
    showOnsError(ERROR_TARGET, "Please select a CSV file first.");
    return;
  }
  const required = [
    [dateCol, "date"],
    [pm25Col, "PM2.5"],
    [deathsCol, "deaths"],
    [populationCol, "population"],
    [humidityCol, "humidity"],
    [precipitationCol, "precipitation"],
    [tmaxCol, "maximum temperature"],
    [windSpeedCol, "wind speed"],
  ];
  const missing = required.find(([val]) => !val);
  if (missing) {
    showOnsError(ERROR_TARGET, `Please select a ${missing[1]} column`);
    return;
  }

  const analyseBtn = getEl("t8Analyse");
  hideOnsError(ERROR_TARGET);
  analyseBtn.classList.add("ons-is-loading");

  const formFile = new FormData();
  formFile.append("file", file);
  formFile.append("date_col", dateCol);
  if (regionCol) formFile.append("region_col", regionCol);
  formFile.append("pm25_col", pm25Col);
  formFile.append("deaths_col", deathsCol);
  formFile.append("population_col", populationCol);
  formFile.append("humidity_col", humidityCol);
  formFile.append("precipitation_col", precipitationCol);
  formFile.append("tmax_col", tmaxCol);
  formFile.append("wind_speed_col", windSpeedCol);
  formFile.append("max_lag", maxLag);
  formFile.append("df_seasonal", dfSeasonal);
  formFile.append("moving_average_window", movingAverageWindow);
  formFile.append("attr_thr", attrThr);
  if (referenceStandards) formFile.append("reference_standards", referenceStandards);
  if (yearsFilter) formFile.append("years_filter", yearsFilter);
  if (regionsFilter) formFile.append("regions_filter", regionsFilter);
  formFile.append("include_national", includeNational);
  formFile.append("run_power", runPower);

  fetch("/airpollution", {
    method: "POST",
    body: formFile,
  })
    .then(async (response) => {
      if (!response.ok) {
        analyseBtn.classList.remove("ons-is-loading");
        const errorData = await parseErrorResponse(response);
        showOnsErrorEnhanced(ERROR_TARGET, errorData);
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      AirPollutionResponse = data ?? {};

      // Populate the reference-standard dropdown from the analysis results keys.
      const dropdown = getEl("t8groupDropdown");
      if (dropdown) {
        dropdown.innerHTML = '<option value="">Select an option</option>';
        const analysisResults = AirPollutionResponse.analysis_results || {};
        Object.keys(analysisResults).forEach((refName) => {
          const opt = document.createElement("option");
          opt.value = refName;
          opt.text = refName;
          dropdown.add(opt);
        });
      }

      analyseBtn.classList.remove("ons-is-loading");
      hideOnsError(ERROR_TARGET);
      getEl("airPollutionResults").style.visibility = "visible";
      getEl("tab_air-pollution-view-results")?.click();
    })
    .catch((error) => {
      analyseBtn.classList.remove("ons-is-loading");
      if (!error.message.includes("HTTP error")) {
        showOnsErrorEnhanced(ERROR_TARGET, "Processing error. Please check your inputs.");
      }
      console.error("Error fetching data from the api:", error);
    });
});

// Air pollution downloads
on("downloadAirPollutionMeta", "click", function () {
  if (!AirPollutionResponse?.meta_results) return;
  const csv = convertObjectToCSV(AirPollutionResponse.meta_results);
  downloadCSV(csv, "air_pollution_meta_results.csv");
});

on("downloadAirPollutionAttr", "click", function () {
  const refName = getValue("t8groupDropdown");
  const analysis = AirPollutionResponse?.analysis_results?.[refName];
  if (!analysis) return;
  const csv = convertObjectToCSV(analysis);
  downloadCSV(csv, `air_pollution_attributable_${refName || "results"}.csv`);
});

// Upload data when button clicked, access API and plot results
on("t0Analyse", "click", async function (e) {
  e.preventDefault();

  // Ensure desc stats are remade
  if (DescStatsBlob) DescStatsBlob = null;

  const file = document.getElementById("t0csvInput").files[0];

  const t0DatasetName = document.getElementById("t0TitleBox").value;
  const t0DisaggCol = document.getElementById("t0AggCol").value;
  const t0DependentCol = document.getElementById("t0DepColName").value;
  const t0IndCol = getMultiSelectValues("t0IndCol[]");

  const t0PlotScatter = document.getElementById("plotScat").checked;
  const t0PlotDists = document.getElementById("plotDist").checked;
  const t0PlotMA = document.getElementById("plotMA").checked;
  const t0PlotCorr = document.getElementById("plotCor").checked;
  const t0PlotNA = document.getElementById("plotNA").checked;

  // Assign variables if they are needed for plots
  let [t0CorrMethod, t0DistCols, t0Timeseries, t0MACols, t0MASides, t0MADays] = Array(6).fill(null);
  if (t0PlotMA) {
    t0Timeseries = document.getElementById("t0DateCol").value;
    t0MACols = getMultiSelectValues("t0maCols[]");
    t0MASides = document.getElementById("t0maSidesOption").value;
    t0MADays = document.getElementById("t0maDaysVal").value;
    if (!t0Timeseries) {
      alert("Please select a timeseries column for the moving average.");
      return;
    }
    if (t0MACols.length == 0) {
      alert("Please select at least one column for the moving average.");
      return;
    }
  }
  if (t0PlotCorr) t0CorrMethod = document.getElementById("t0CorMethodCol").value;
  if (t0PlotDists) {
    t0DistCols = getMultiSelectValues("t0ColDist[]");
    if (t0DistCols.length == 0) {
      alert("Please select at least one column for the distributions.");
      return;
    }
  }

  if (!file) {
    alert("Please select a CSV file first.");
    return;
  }
  if (!t0DependentCol) {
    alert("Please select a dependent column.");
    return;
  }
  if (t0IndCol.length == 0) {
    alert("Please select at least 1 independent column.");
    return;
  }

  document.getElementById("t0spinner").style.visibility = "visible";
  document.getElementById("t0apiMessage").innerHTML = "Sending data";

  let formFile = new FormData();
  formFile.append("file", file);
  formFile.append("aggregation_column", t0DisaggCol);
  formFile.append("dataset_title", t0DatasetName);
  formFile.append("dependent_col", t0DependentCol);
  formFile.append("independent_cols", t0IndCol);
  formFile.append("plot_correlation", t0PlotCorr);
  formFile.append("plot_dist_hists", t0PlotDists);
  formFile.append("plot_ma", t0PlotMA);
  formFile.append("plot_na_counts", t0PlotNA);
  formFile.append("plot_scatter", t0PlotScatter);
  formFile.append("correlation_method", t0CorrMethod);
  formFile.append("dist_columns", t0DistCols);
  formFile.append("ma_days", t0MADays);
  formFile.append("ma_sides", t0MASides);
  formFile.append("ma_columns", t0MACols);
  formFile.append("timeseries_col", t0Timeseries);

  fetch("/descriptive_stats", {
    method: "POST",
    body: formFile,
  })
    .then((response) => {
      if (!response.ok) {
        document.getElementById("t0spinner").style.visibility = "hidden";
        document.getElementById("t0apiMessage").innerHTML =
          '<p class="text-lg text-red-400">Processing Error</p>';
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      DescStatsPath = data.desc_stats_path[0];
      DescStatsFname = data.desc_stats_path[1] + ".zip";

      // Switch to Results tab
      document.getElementById("DescStatsViewResultsTab").click();

      document.getElementById("t0spinner").style.visibility = "hidden";
      document.getElementById("t0apiMessage").innerHTML = "";
    })
    .catch((error) => {
      console.error("Error fetching data from the api:", error);
    });
});

// Diarrhea Analyse
let DiarrheaZipPath = null;
let DiarrheaZipFname = null;
let DiarrheaZipData = null;

on("t4analyse", "click", async function (e) {
  e.preventDefault();

  // Ensure save is remade
  if (DiarrheaBlob) DiarrheaBlob = null;

  const healthFile = document.getElementById("t4healthInput").files[0];
  const climateFile = document.getElementById("t4climateInput").files[0];
  const geoFile = document.getElementById("t4sfInput").files[0];

  // Get all t4 (waterborne) input values
  const t4region = document.getElementById("t4region").value;
  const t4district = document.getElementById("t4district").value;
  const t4date = document.getElementById("t4date").value;
  const t4year = document.getElementById("t4year").value;
  const t4month = document.getElementById("t4month").value;
  const t4diarrhea_case = document.getElementById("t4diarrhea_case").value;
  const t4tot_pop = document.getElementById("t4tot_pop").value;
  const t4tmin = document.getElementById("t4tmin").value;
  const t4tmean = document.getElementById("t4tmean").value;
  const t4tmax = document.getElementById("t4tmax").value;
  const t4rainfall = document.getElementById("t4rainfall").value;
  const t4r_humidity = document.getElementById("t4r_humidity").value;
  const t4runoff = document.getElementById("t4runoff").value;
  const t4geometry = document.getElementById("t4geometry").value;
  const t4spi = document.getElementById("t4spi").value;

  // Multi-select for basis matrices
  const t4basisMatrices = getMultiSelectValues("t4basisMatrices[]");
  const t4inlaParams = getMultiSelectValues("t4inlaParams[]");

  // param_term is now a single text input
  const t4param_term = document.getElementById("t4param_term").value;

  // Additional parameters
  const t4max_lag = document.getElementById("t4max_lag").value;
  const t4level = document.getElementById("t4level").value;
  const t4param_threshold = document.getElementById("t4param_threshold").value;
  if (!healthFile) {
    alert("Please select a health CSV file first.");
    return;
  }
  if (!climateFile) {
    alert("Please select a climate CSV file first.");
    return;
  }
  if (!geoFile) {
    alert("Please select a shapefile ZIP first.");
    return;
  }
  if (t4basisMatrices.length == 0) {
    alert("Please select select at least one column for 'Basis Matrices Choices'.");
    return;
  }
  if (t4inlaParams.length == 0) {
    alert("Please select select at least one column for 'Inla Parameters'.");
    return;
  }
  if (t4param_threshold <= 0) {
    alert("Parameter threshold must be greater than 0.");
    return;
  }
  if (t4max_lag <= 0) {
    alert("Max lag must be greater than or equal to 0.");
    return;
  }

  document.getElementById("t4spinner").style.visibility = "visible";
  document.getElementById("t4apiMessage").innerHTML = "Sending data";

  let formFile = new FormData();
  formFile.append("health_file", healthFile);
  formFile.append("climate_file", climateFile);
  formFile.append("geo_zip_file", geoFile, "geo_file.zip");

  formFile.append("region_col", t4region);
  formFile.append("district_col", t4district);
  formFile.append("date_col", t4date);
  formFile.append("year_col", t4year);
  formFile.append("month_col", t4month);
  formFile.append("diarrhea_case_col", t4diarrhea_case);

  formFile.append("tot_pop_col", t4tot_pop);
  formFile.append("tmin_col", t4tmin);
  formFile.append("tmean_col", t4tmean);
  formFile.append("tmax_col", t4tmax);
  formFile.append("rainfall_col", t4rainfall);
  formFile.append("r_humidity_col", t4r_humidity);
  formFile.append("runoff_col", t4runoff);
  formFile.append("geometry_col", t4geometry);
  formFile.append("spi_col", t4spi);

  // Multi-select as comma-separated string
  formFile.append("basis_matrices_choices", t4basisMatrices);
  formFile.append("inla_param", t4inlaParams);

  formFile.append("param_term", t4param_term);
  formFile.append("max_lag", t4max_lag);
  formFile.append("level", t4level);
  formFile.append("param_threshold", t4param_threshold);

  fetch("/waterborne", {
    method: "POST",
    body: formFile,
  })
    .then((response) => {
      if (!response.ok) {
        document.getElementById("t4spinner").style.visibility = "hidden";
        document.getElementById("t4apiMessage").innerHTML =
          '<p class="text-lg text-red-400">Processing Error</p>';
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      DiarrheaZipPath = data.result_json.output_path[0];
      DiarrheaZipFname = data.result_json.output_fname[0];

      // Switch to Results tab
      document.getElementById("WaterborneViewResultsTab").click();

      document.getElementById("t4spinner").style.visibility = "hidden";
      document.getElementById("t4apiMessage").innerHTML = "";
    })
    .catch((error) => {
      console.error("Error fetching data from the api:", error);
    });
});

// Malaria Analyse
let MalariaZipPath = null;
let MalariaZipFname = null;
let MalariaZipData = null;

on("t5analyse", "click", async function (e) {
  e.preventDefault();

  const ERROR_TARGET = "t5ApiError";

  // Ensure save is remade
  if (MalariaBlob) MalariaBlob = null;

  // Files
  const healthFile = getFile("t5healthInput");
  const climateFile = getFile("t5climateInput");
  const geoFile = getFile("t5sfInput");

  // Values
  const t5region = getValue("t5region");
  const t5district = getValue("t5district");
  const t5date = getValue("t5date");
  const t5year = getValue("t5year");
  const t5month = getValue("t5month");
  const t5malaria_case = getValue("t5malaria_case");
  const t5tot_pop = getValue("t5tot_pop");
  const t5tmin = getValue("t5tmin");
  const t5tmean = getValue("t5tmean");
  const t5tmax = getValue("t5tmax");
  const t5rainfall = getValue("t5rainfall");
  const t5r_humidity = getValue("t5r_humidity");
  const t5runoff = getValue("t5runoff");
  const t5geometry = getValue("t5geometry");
  const t5ndvi = getValue("t5ndvi");
  const t5spi = getValue("t5spi");

  const t5basisMatrices = getCheckboxValues("t5basisMatricesList");
  const t5inlaParams = getCheckboxValues("t5inlaParamsList");

  const t5param_term = getValue("t5param_term");
  const t5max_lag = getNumber("t5max_lag");
  const t5level = getValue("t5level");
  const t5param_threshold = getNumber("t5param_threshold");

  // Basic validation
  if (!healthFile) {
    showOnsError(ERROR_TARGET, "Please select a health CSV file first.");
    return;
  }
  if (!climateFile) {
    showOnsError(ERROR_TARGET, "Please select a climate CSV file first.");
    return;
  }
  if (!geoFile) {
    showOnsError(ERROR_TARGET, "Please select a shapefile ZIP first.");
    return;
  }

  if (t5param_threshold === null || t5param_threshold <= 0) {
    showOnsError(ERROR_TARGET, "Parameter threshold must be a number greater than 0.");
    return;
  }

  if (t5max_lag === null || t5max_lag < 0) {
    showOnsError(ERROR_TARGET, "Max lag must be greater than or equal to 0.");
    return;
  }

  if (!t5tot_pop) {
    showOnsError(ERROR_TARGET, "Please select the total population column.");
    return;
  }

  if (!t5malaria_case) {
    showOnsError(ERROR_TARGET, "Please select the malaria cases column.");
    return;
  }

  if (!t5param_term) {
    showOnsError(ERROR_TARGET, "Please select a parameter term");
    return;
  }

  if (!t5basisMatrices.length) {
    showOnsError(ERROR_TARGET, "Please select at least one option for 'Basis Matrices Choices'.");
    return;
  }

  if (!t5inlaParams.length) {
    showOnsError(ERROR_TARGET, "Please select at least one option for 'INLA Parameters'.");
    return;
  }

  // Loading
  hideOnsError(ERROR_TARGET);
  document.getElementById("t5analyse").classList.add("ons-is-loading");
  document.getElementById("apiMessage").innerHTML = "Sending data";

  let formFile = new FormData();
  formFile.append("health_file", healthFile);
  formFile.append("climate_file", climateFile);
  formFile.append("geo_zip_file", geoFile, "geo_file.zip");

  formFile.append("region_col", t5region);
  formFile.append("district_col", t5district);
  formFile.append("date_col", t5date);
  formFile.append("year_col", t5year);
  formFile.append("month_col", t5month);
  formFile.append("malaria_case_col", t5malaria_case);

  formFile.append("tot_pop_col", t5tot_pop);
  formFile.append("tmin_col", t5tmin);
  formFile.append("tmean_col", t5tmean);
  formFile.append("tmax_col", t5tmax);
  formFile.append("rainfall_col", t5rainfall);
  formFile.append("r_humidity_col", t5r_humidity);
  formFile.append("runoff_col", t5runoff);
  formFile.append("geometry_col", t5geometry);
  formFile.append("spi_col", t5spi);
  formFile.append("ndvi_col", t5ndvi);

  // Multi-select as comma-separated string
  formFile.append("basis_matrices_choices", t5basisMatrices);
  formFile.append("inla_param", t5inlaParams);

  formFile.append("param_term", t5param_term);
  formFile.append("max_lag", t5max_lag);
  formFile.append("level", t5level);
  formFile.append("param_threshold", t5param_threshold);

  fetch("/vectorborne", {
    method: "POST",
    body: formFile,
  })
    .then(async (response) => {
      if (!response.ok) {
        // Finished loading, error state
        document.getElementById("t5analyse").classList.remove("ons-is-loading");
        const errorData = await parseErrorResponse(response);
        showOnsErrorEnhanced(ERROR_TARGET, errorData);
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      if (data && data.result_json) {
        // api res
        MalariaZipPath = data.result_json.output_path[0];
        MalariaZipFname = data.result_json.output_fname[0];
        hideOnsError(ERROR_TARGET);
        document.getElementById("t5analyse").classList.remove("ons-is-loading");
      } else if (data) {
        // mock api res
        vectorborneCurveData = data.curve_data || vectorborneCurveData;
        vectorborneBarData = data.bar_data || vectorborneBarData;
        vectorborneScatterData = data.scatter_data || vectorborneScatterData;
        vectorborneGroups = vectorborneCurveData ? Object.keys(vectorborneCurveData) : [];
        if (vectorborneCurveData) plotCurveVB("National");
        if (vectorborneBarData) plotBarVB();
        if (vectorborneScatterData) plotScatterVB();
        hideOnsError(ERROR_TARGET);
        document.getElementById("t5analyse").classList.remove("ons-is-loading");
      } else {
        console.warn("Vectorborne response did not include expected payload.");
      }

      document.getElementById("tab_vector-borne-view-results").click();
      setTimeout(resizeVectorbornePlots, 100);
    })
    .catch((error) => {
      document.getElementById("t5analyse").classList.remove("ons-is-loading");
      // Only show generic error if not already shown by structured error handler
      if (!error.message.includes("HTTP error")) {
        showOnsErrorEnhanced("t5ApiError", "Processing error. Please check your inputs.");
      }
      console.error("Error fetching data from the api:", error);
    });
});

on("t1dateCol", "change", function () {
  if (!csvFile) {
    alert("Please select a CSV file first.");
    return;
  }
  const selectedColumnName = this.value;
  updateDateRange(csvFile, selectedColumnName); // Call the new function
});

on("t7timeCol", "change", function () {
  if (!csvFile) {
    alert("Please select a CSV file first.");
    return;
  }
  const selectedColumnName = this.value;
  updateDateRange(csvFile, selectedColumnName); // Call the new function
});

// on("subgeoCol", "change", function () {
//   var checkboxA = document.getElementById("disaggCheck");
//   var checkboxB = document.getElementById("metaCheck");
//   if (document.getElementById("subgeoCol").value === '') {
//     checkboxB.checked = false;
//     checkboxA.checked = false;
//     checkboxB.disabled = true;
//     checkboxA.disabled = true;
//   } else {
//     checkboxA.disabled = false;
//     checkboxB.disabled = false;
//     checkboxA.checked = true;
//     checkboxB.checked = true;
//   }
// });

on("subgeoCol", "change", function () {
  var checkbox = document.getElementById("metaCheck");
  if (document.getElementById("subgeoCol").value === "") {
    checkbox.checked = false;
    checkbox.disabled = true;
  } else {
    checkbox.disabled = false;
    checkbox.checked = true;
  }
});

// H+C Plot Listeners
on("groupDropdown", "change", plotLine);
on("groupDropdown", "change", plotBar);
// on("groupDropdown", "change", plotTable);

// WF Plot Listeners
on("t2groupDropdown", "change", function () {
  plotWildfiresRR("wildfiresRRPlot");
  if (document.getElementById("t2-results-by-region-1").checked) {
    const selectedGroup = document.getElementById("t2groupDropdown").value;
    plotWildfiresANAR("wildfiresAnPlot", selectedGroup, "AR");
    plotWildfiresARPM("wildfiresAfPlot", selectedGroup);
  }
});

// MH Plot Listeners
on("t7groupDropdown", "change", function () {
  const selectedGroup = getValue("t7groupDropdown");
  plotLineMH("mentalHealthRRPlot");
  plotScatterMH("mentalHealthARYRPlot");
  plotBarMHARPM("mentalHealthARMPlot", selectedGroup);
});

// function setCheckboxState1() {
//   var checkboxA = document.getElementById("disaggCheck");
//   var checkboxB = document.getElementById("metaCheck");

//   // When Disagg is unchecked then uncheck Meta
//   if (!checkboxA.checked) {
//     // If "A" is false then "B" must be true
//     checkboxB.checked = false;
//   }

// }

// function setCheckboxState2() {
//   var checkboxA = document.getElementById("disaggCheck");
//   var checkboxB = document.getElementById("metaCheck");

//   // Can only check Meta if Disagg is checked
//   if (!checkboxA.checked) {
//     // If "A" is false then "B" must be true
//     checkboxB.checked = false;
//   }
// }

function openPane(evt, paneName) {
  // Declare all variables
  var i, tabcontent, tablinks;

  // Get all elements with class="tabcontent" and hide them
  tabcontent = document.getElementsByClassName("tabcontent");
  for (i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }

  // Get all elements with class="tablinks" and remove the class "active"
  tablinks = document.getElementsByClassName("tablinks");
  for (i = 0; i < tablinks.length; i++) {
    tablinks[i].className = tablinks[i].className.replace(" active", "");
  }

  // Show the current tab, and add an "active" class to the button that opened the tab
  document.getElementById(paneName).style.display = "block";
  evt.currentTarget.className += " active";
}

// Get the element with id="defaultOpen" and click on it
getEl("DescStatsSelectFileTab")?.click();

class IndicatorBanner extends HTMLElement {
  constructor() {
    super();
  }

  connectedCallback() {
    this.innerHTML = `
      <div class="p-2 px-8 text-gray-100 bg-blue-900 rounded shadow-lg">
      <p>
        On this page you can calculate indicators using your own data via the platform.
        Information about the indicators and their methods will be found under the statistical framework.
        The underlying code for these indicator calculators is open source and will be available on request via Github.
        Please contact: 
        
        <a href="mailto:climate.health@ons.gov.uk" class="hover:underline"
          >climate.health@ons.gov.uk <i class="fa fa-envelope-o" aria-hidden="true"></i></a
        >.
      </p>
      </div>
      `;
  }
}

customElements.define("indicator-banner", IndicatorBanner);

// Monitor Collapsibles
var collapsibles = document.getElementsByClassName("collapsible-options");
var i;

for (i = 0; i < collapsibles.length; i++) {
  collapsibles[i].addEventListener("click", function () {
    this.classList.toggle("active");
    var content = this.nextElementSibling;
    if (content.style.maxHeight) {
      content.style.maxHeight = null;
      content.style.overflow = null;
    } else {
      content.style.maxHeight = "330" + "px";
      content.style.overflow = "visible";
    }
  });
  if (collapsibles[i].textContent != "Additional Plotting Options") collapsibles[i].click();
}

function toggleHint(btn) {
    var baseId = btn.getAttribute("data-hint-toggle");
    if (!baseId) return;

    var hint = document.getElementById(baseId + "-hint");
    if (!hint) return;

    var isHidden = hint.classList.contains("ons-u-vh");

    // Show/hide hint text
    hint.classList.toggle("ons-u-vh", !isHidden);

    // Keep aria-expanded in sync
    btn.setAttribute("aria-expanded", String(isHidden));
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-hint-toggle]");
    if (!btn) return;
    toggleHint(btn);
  });
