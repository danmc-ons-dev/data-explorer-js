let csvData = []; // Global variable to hold CSV data
let averages = {}; // Global variable to hold average values

// Load CSV data
Papa.parse("/static/data/long_country_ann_temp_change.csv", {
  download: true,
  header: true,
  complete: (results) => {
    csvData = results.data;
    calculateAverages(); // Calculate averages after CSV data is loaded
    initMap(); // Initialize the map after CSV data is loaded
  },
});

// Step 1: Calculate the average value for each feature
function calculateAverages() {
  csvData.forEach((row) => {
    let featureId = row["ISO2"]; // Replace with the actual identifier key
    let value = parseFloat(row["sur_temp_change"]); // Replace with the actual value column
    if (!averages[featureId]) {
      averages[featureId] = { sum: 0, count: 0 };
    }
    averages[featureId].sum += value;
    averages[featureId].count++;
  });

  for (let id in averages) {
    averages[id] = averages[id].sum / averages[id].count;
  }

  console.log(averages);
}

function getColor(value) {
  // Define how to color regions based on value
  // Example ranges, modify as needed
  return value > 1
    ? "#800026"
    : value > 0.5
    ? "#BD0026"
    : value > 0.4
    ? "#E31A1C"
    : value > 0.3
    ? "#FC4E2A"
    : value > 0.2
    ? "#FD8D3C"
    : value > 0.1
    ? "#FEB24C"
    : value > 0
    ? "#FED976"
    : "#FFEDA0";
}

// Step 3: Apply the color to each feature
function style(feature) {
  let featureId = feature.properties.ISO; // Adjust this to match your feature's identifier
  let averageValue = averages[featureId] || 0;

  return {
    fillColor: getColor(averageValue),
    weight: 2,
    opacity: 1,
    color: "white",
    fillOpacity: 0.7,
  };
}

function addLegend(map) {
  var legend = L.control({ position: "bottomright" });

  legend.onAdd = function (map) {
    var div = L.DomUtil.create("div", "info legend"),
      grades = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 1], // Define the breakpoints
      labels = [],
      from,
      to;

    // Loop through the intervals and generate a label with a colored square for each
    for (var i = 0; i < grades.length; i++) {
      from = grades[i];
      to = grades[i + 1];

      labels.push(
        '<i style="background:' +
          getColor(from + 0.01) +
          '; width: 18px; height: 18px; float: left; margin-right: 8px; opacity: 0.7;"></i> ' +
          from +
          (to ? "&ndash;" + to : "+")
      );
    }

    div.innerHTML = labels.join("<br>");
    div.style.fontSize = "22px"; // Increase font size

    return div;
  };

  legend.addTo(map);
}

function initMap() {
  // Initialize your map and add GeoJSON layer
  const map = L.map("map").setView([50, 0], 3);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  fetch("/static/data/countries.geojson")
    .then((response) => response.json())
    .then((geojsonData) => {
      L.geoJson(geojsonData, {
        style: style, // Apply the style function
        onEachFeature: onEachFeature,
      }).addTo(map);
    })
    .catch((error) => {
      console.error("Error loading GeoJSON:", error);
    });

  addLegend(map); // Add the legend to the map
}

let selectedLayer = null; // Variable to hold the currently selected layer

function onEachFeature(feature, layer) {
  // Set the initial style for the layer (if needed)
  layer.setStyle(style(feature));

  // Mouseover event
  if (feature.properties && feature.properties.COUNTRY) {
    layer.on({
      mouseover: function (e) {
        this.setStyle({
          weight: 3,
          color: "gray",
          fillOpacity: 0.7,
        });
        if (!L.Browser.ie && !L.Browser.opera) {
          this.bringToFront();
        }
        this.bindPopup(feature.properties.COUNTRY).openPopup();
      },
      mouseout: function (e) {
        if (selectedLayer !== e.target) {
          e.target.setStyle(style(feature)); // Reset to original style
        }
      },
      click: function (e) {
        // Reset style of the previously selected layer
        if (selectedLayer) {
          selectedLayer.setStyle(style(selectedLayer.feature));
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
            <div class="bg-gray-100 p-2 rounded">
                <h2 class="text-xl font-bold">Details</h2>
                <div class="mb-2">`;

        for (let key in properties) {
          popupContent += `<p class="text-sm"><strong>${key}:</strong> ${properties[key]}</p>`;
        }

        popupContent += `<div>
                <a href="upload.html" class="text-blue-500 text-xl hover:underline">Upload data</a>
            </div>
                <a href="data_plots.html" class="text-blue-500 text-xl hover:underline">Explore data</a>
            </div>
        `;

        layer.bindPopup(popupContent).openPopup(); // Bind the content to the popup and open it

        // Update Plotly chart
        const featureId = feature.properties.ISO; // Adjust this as needed
        const featureData = csvData.filter((row) => row.ISO2 === featureId);
        updatePlotlyChart(featureData);
      },
    });
  }
}

function updatePlotlyChart(featureData) {
  const time = featureData.map((row) => row.year);
  const indicator = featureData.map((row) => row.sur_temp_change);

  const data = [
    {
      x: time,
      y: indicator,
      type: "scatter",
      mode: "lines+points",
      marker: { color: "blue", size: 100 },
    },
  ];

  const layout = {
    title: `Change in temperature`,
    xaxis: { title: "Year" },
    yaxis: { title: "Change in temperature (°C)" },
  };

  Plotly.newPlot("plotlyChart", data, layout);
}
