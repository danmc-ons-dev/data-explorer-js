let rawData = [];
let groupedData = [];
let selectedGeo = [];
let clickedGeo = [];
let colorMap;
let countries;

const map = L.map("map").setView([50, 0], 1);
let shapefileLayer = L.layerGroup().addTo(map);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 3,
  attribution: "© OpenStreetMap contributors",
}).addTo(map);

fetch("/static/data/shp/countries_incl_uk.geojson")
  .then((response) => response.json())
  .then((data) => {
    countries = data;
    L.geoJson(countries, {
      fillColor: "transparent",
      color: "black",
      weight: 0.5,
      opacity: 0.5,
      onEachFeature: function (feature, layer) {
        let popupContent = `
            <div class="bg-slate-500 rounded">
                <h2 class="text-2xl font-bold">No data for ${feature.properties.COUNTRY}</h2>
                <br>
                <a href="/upload" class="text-green-500 text-2xl hover:underline">Upload data here</a>
            </div>`;

        layer.bindPopup(popupContent).openPopup();

        layer.on({
          mouseover: function (e) {
            let layer = e.target;
            layer.setStyle({
              fillColor: "gray",
              color: "black",
              weight: 2,
              opacity: 1,
            });
          },
          mouseout: function (e) {
            if (selectedLayer !== e.target) {
              let layer = e.target;
              layer.setStyle({
                fillColor: "transparent",
                color: "black",
                weight: 0.5,
                opacity: 0.5,
              });
            }
          },
        });
      },
    }).addTo(map);
  });

fetch("/static/data/csv/countries_color_map.json")
  .then((response) => response.json())
  .then((data) => {
    colorMap = data;
  });

fetch("/populate_indicator_dropdown/")
  .then((response) => response.json())
  .then((data) => {
    const dropdown = document.getElementById("indicator_dropdown");

    dropdown.innerHTML = '<option value="0">No indicator selected</option>';

    data.forEach((item) => {
      const option = document.createElement("option");
      option.value = item;
      option.textContent = item;
      dropdown.appendChild(option);
    });
  })
  .catch((error) => console.error("Error:", error));

function indicatorPlot(selectedGeo) {
  let data = groupedData;

  let traces = [];

  let plotTitle = rawData[0].exposure_type;
  let xaxisTitle = rawData[0].exposure_unit;
  let yaxisTitle = rawData[0].outcome_unit;

  for (let i = 0; i < selectedGeo.length; i++) {
    let filteredData = data.filter((row) => row.geography === selectedGeo[i]);

    let xvals = filteredData.map((row) => row["exposure_value"]);
    let yvals = filteredData.map((row) => row["outcome_value"]);

    let yLower = filteredData.map((row) => row["outcome_value_lower"]);
    let yUpper = filteredData.map((row) => row["outcome_value_higher"]);

    let traceData = {
      x: xvals,
      y: yvals,
      type: "scatter",
      mode: "lines+markers",
      name: selectedGeo[i],
      line: {
        width: 5,
        color: colorMap[selectedGeo[i]],
      },
      marker: {
        size: 10,
        color: colorMap[selectedGeo[i]],
      },
    };

    let traceLowerBound = {
      x: xvals,
      y: yLower,
      line: { width: 0 },
      marker: { color: "444" },
      mode: "lines",
      name: "Upper bound",
      type: "scatter",
      showlegend: false,
    };

    let traceUpperBound = {
      x: xvals,
      y: yUpper,
      fill: "tonexty",
      fillcolor: "rgba(68, 68, 68, 0.3)",
      line: { width: 0 },
      marker: { color: "444" },
      mode: "lines",
      name: "Lower bound",
      type: "scatter",
      showlegend: false,
    };

    traces.push(traceData);
    traces.push(traceLowerBound);
    traces.push(traceUpperBound);
  }

  const layout = {
    title: plotTitle,
    paper_bgcolor: "rbga(255,255,255,1)",
    plot_bgcolor: "rbga(255,255,255,1)",
    xaxis: {
      title: xaxisTitle,
    },
    yaxis: {
      title: yaxisTitle,
    },
    font: {
      family: "Arial, sans-serif",
      size: 14,
      color: "black",
    },
  };

  Plotly.newPlot("plotlyChart", traces, layout);
}

let selectedLayer = null; // Variable to hold the currently selected layer
let geoJson = null; // Variable to hold the currently selected layer

function mapPlot() {
  shapefileLayer.clearLayers();

  let selected_row = document.getElementById("indicator_dropdown").value;

  if (selected_row != "0") {
    fetch(`/get_shapefile_data/${selected_row}`)
      .then((response) => response.json())
      .then((data) => {
        // Plot the data
        geoJson = data;

        L.geoJson(geoJson, {
          style: function (feature) {
            let colors = colorMap[feature.properties.geography];
            return { color: colors, weight: 2, opacity: 1, fillOpacity: 0.5 };
          },
          onEachFeature: onEachFeature,
        }).addTo(shapefileLayer);
      })
      .catch((error) => console.error("Error:", error));
  } else {
    addBaseMap();
  }
}

function onEachFeature(feature, layer) {
  layer.on({
    mouseover: function (e) {
      let layer = e.target;
      layer.setStyle({
        weight: 5, // Highlight the border
        color: colorMap[feature.properties.geography],
        fillOpacity: 0.7,
      });
      if (!L.Browser.ie && !L.Browser.opera) {
        layer.bringToFront();
      }
      layer.bindPopup(feature.properties.geography).openPopup(); // Show popup with the name property
    },
    mouseout: function (e) {
      if (selectedLayer !== e.target) {
        let layer = e.target;
        layer.setStyle({
          fillColor: colorMap[feature.properties.geography],
          weight: 2,
          opacity: 1,
          fillOpacity: 0.5,
        });
      }
    },
    click: function (e) {
      // Reset style of the previously selected layer
      if (selectedLayer) {
        selectedLayer.setStyle({
          weight: 5, // Highlight the border
          color: colorMap[feature.properties.geography],
          fillOpacity: 0.5,
        });
      }

      // Highlight the clicked layer
      selectedLayer = e.target;
      selectedLayer.setStyle({
        weight: 5,
        color: "gold", // Highlight color
        fillOpacity: 0.7,
      });

      const properties = feature.properties;

      // Construct the content for the popup using Tailwind classes
      let popupContent = `
            <div class="rounded">
                <h2 class="text-2xl font-bold">Dataset details</h2>
                <div class="mb-2">`;

      for (let key in properties) {
        popupContent += `<p class="text-xl"><strong>${key}:</strong> ${properties[key]}</p>`;
      }

      if (properties.sub_geography != null) {
        popupContent += `<div>
                <a href="/upload" class="text-green-500 text-xl hover:underline">Upload more data</a>
            </div>
            <br>
                <a href="/data_plots" class="text-green-500 text-xl hover:underline">Explore disaggregated data</a>
            </div>
            `;
      } else {
        popupContent += `<div>
        <a href="/data_plots" class="text-green-500 text-2xl hover:underline">Explore data</a>
        </div>
        <div>
        <a href="/upload" class="text-green-500 text-2xl hover:underline">Upload more data</a>
        </div>
        <br>
        `;
      }

      layer.bindPopup(popupContent).openPopup(); // Bind the content to the popup and open it

      // Update Plotly chart
      if (!clickedGeo.includes(feature.properties.geography)) {
        clickedGeo.push(feature.properties.geography);
      } // Adjust this as needed
      indicatorPlot(clickedGeo);
    },
  });
}

document
  .getElementById("indicator_dropdown")
  .addEventListener("change", function () {
    // const selectedLAD22NM = this.value;
    let selectedIndicator = [];

    for (let option of indicator_dropdown.options) {
      if (option.selected) {
        selectedIndicator.push(option.value);
      }
    }
    if (selectedIndicator) {
      let selected_row = document.getElementById("indicator_dropdown").value;
      fetch(`/plot_indicator_data/${selected_row}`)
        .then((response) => response.json())
        .then((data) => {
          rawData = JSON.parse(data.full_query);
          groupedData = JSON.parse(data.grouped_query);
          selectedGeo = new Set(groupedData.map((item) => item.geography));
          selectedGeo = Array.from(selectedGeo);
          
          indicatorPlot(selectedGeo);
          mapPlot(selectedIndicator);
        });
    }
  });

//////////////////////////////////////////
