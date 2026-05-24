let averages;
let geojsonData;
let temps;
let all_averages;

// const get_averages_path = '/get_averages';
// const get_averages_url = `${window.location.protocol}//${window.location.host}${path}`

function buildUrl(path) {
  return `${window.location.protocol}//${window.location.host}${path}`
}

fetch(buildUrl("/get_averages"))
  .then((response) => response.json())
  .then((data) => {
    temps = JSON.parse(data.temps);
    averages = JSON.parse(data.averages);
    all_averages = JSON.parse(data.all_averages);
    PlotlyChart();
  });

fetch("/get_shapefile_joined")
  .then((response) => response.json())
  .then((data) => {
    geojsonData = data;
    console.log(geojsonData);
    initMap(geojsonData);
  });

function getColor(d) {
  return d > 1.0
    ? "#a30f15"
    : d > 0.8
    ? "#ca181d"
    : d > 0.6
    ? "#ee3a2c"
    : d > 0.4
    ? "#fb694a"
    : d > 0.2
    ? "#fc9272"
    : d > 0
    ? "#fcbba1"
    : d > -0.2
    ? "#fee0d2"
    : "#fee0d2";
}

function addLegend(map) {
  var legend = L.control({ position: "bottomright" });

  legend.onAdd = function (map) {
    var div = L.DomUtil.create("div", "info legend"),
      grades = [-0.2, 0, 0.2, 0.4, 0.6, 0.8, 1.0],
      labels = ["<strong> Avg. ann. change </strong>"],
      from,
      to;

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
    div.style.fontSize = "20px"; // Increase font size

    return div;
  };

  legend.addTo(map);
}

function initMap(geoData) {
  // Initialize your map and add GeoJSON layer
  const map = L.map("map").setView([50, 0], 2);
  L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  L.geoJson(geoData, {
    style: style,
    onEachFeature: onEachFeature,
  }).addTo(map);
  addLegend(map);
}

// Apply the color to each feature
function style(feature) {
  return {
    fillColor: feature.properties.color,
    weight: 2,
    opacity: 1,
    color: "white",
    fillOpacity: 0.7,
  };
}

function PlotlyChart() {
  const time = all_averages.map((row) => row.year);
  const indicator = all_averages.map((row) => row.sur_temp_change);

  const data = [
    {
      x: time,
      y: indicator,
      type: "scatter",
      mode: "lines",
      line: { color: "red", width: 4 },
    },
  ];

  const layout = {
    title: `Global`,
    paper_bgcolor: "rgba(0, 0, 0, 0)",
    plot_bgcolor: "rgba(0, 0, 0, 0",
    xaxis: { title: "Year", range: [1960, 2023] },
    yaxis: { title: "Change in temperature (°C)", range: [-1, 3] },
    font: {
      family: "Arial, sans-serif",
      size: 20,
      color: "black",
    },
  };

  Plotly.newPlot("plotlyChart", data, layout);
}

function updatePlotlyChart(featureData, title) {
  const time = featureData.map((row) => row.year);
  const indicator = featureData.map((row) => row.sur_temp_change);

  const data = [
    {
      x: time,
      y: indicator,
      type: "scatter",
      mode: "lines",
      line: { color: "red", width: 4 },
    },
  ];

  const layout = {
    title: `${title}`,
    paper_bgcolor: "rgba(0, 0, 0, 0)",
    plot_bgcolor: "rgba(0, 0, 0, 0",
    xaxis: { title: "Year", range: [1960, 2023] },
    yaxis: { title: "Change in temperature (°C)", range: [-1, 3] },
    font: {
      family: "Arial, sans-serif",
      size: 20,
      color: "black",
    },
  };

  Plotly.newPlot("plotlyChart", data, layout);
}

let selectedLayer = null; // Variable to hold the currently selected layer

function onEachFeature(feature, layer) {
  layer.setStyle(style(feature));

  // Mouseover event
  if (feature.properties) {
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
        this.bindPopup(feature.properties.geography).openPopup();
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

        // Update Plotly chart
        const featureId = feature.properties.ISO; // Adjust this as needed
        const featureData = temps.filter((row) => row.ISO2 === featureId);
        const title = feature.properties.geography;
        console.log(feature);
        updatePlotlyChart(featureData, title);
      },
    });
  }
}
