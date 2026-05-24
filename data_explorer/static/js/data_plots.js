let parsedData = [];

// Load CSV and shapefile when window loads
window.onload = function () {
  Papa.parse("/static/data/csv/dummy_data_one.csv", {
    header: true,
    download: true,
    dynamicTyping: true,
    complete: function (results) {
      parsedData = results.data;
      populateLAD22NMDropdown(getUniqueValues(parsedData, "LAD22NM"));
    },
  });
  // Load GeoJSON
  fetch("/static/data/shp/dummy_data_las_shapefile.geojson") // Replace with your GeoJSON file path
    .then((response) => response.json())
    .then((data) => {
      geojsonData = data;
    });
};

dataDropdown = document.getElementById("dataColumn");

// Plot region data and map when data column selected
dataDropdown.addEventListener("change", function () {
  // const selectedLAD22NM = this.value;
  let selectedLAD22NM = [];

  for (let option of dataDropdown.options) {
    if (option.selected) {
      selectedLAD22NM.push(option.value);
    }
  }
  if (selectedLAD22NM) {
    plotData(selectedLAD22NM);
    plotOnMap(selectedLAD22NM);
  }
});

// Get unique values from data
function getUniqueValues(data, column) {
  return [...new Set(data.map((item) => item[column]))];
}

// Populate dropdown with regions
function populateLAD22NMDropdown(uniqueLAD22NM) {
  const select = document.getElementById("dataColumn");
  select.innerHTML = ""; // Clear current options
  uniqueLAD22NM.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

// Populate dropdown with regions
function plotData(selectedLAD22NM) {
  let traces = [];

  for (let i = 0; i < selectedLAD22NM.length; i++) {
    console.log(selectedLAD22NM[i]);

    let filteredData = parsedData.filter(
      (row) => row.LAD22NM === selectedLAD22NM[i]
    );
    let xvals = filteredData.map((row) => row["Period"]);
    let yvals = filteredData.map((row) => row["Relative_Risk"]);

    let trace = {
      x: xvals,
      y: yvals,
      type: "scatter",
      mode: "lines+markers",
      name: selectedLAD22NM[i],
      line: { width: 5 },
      marker: { size: 10 },
    };

    traces.push(trace);
  }

  const layout = {
    title: `Relative Risk for ${selectedLAD22NM}`,
    paper_bgcolor: "rgba(0, 0, 0, 0)",
    plot_bgcolor: "rgba(0, 0, 0, 0",
    xaxis: {
      title: "Period",
    },
    yaxis: {
      title: "Relative Risk",
    },
    font: {
      family: "Arial, sans-serif",
      size: 20,
      color: "black",
    },
  };

  Plotly.newPlot("plotlyChart", traces, layout);
}

let ladLayer; // Holds the plotted region

// Plot region on map
function plotOnMap(selectedLAD22NM) {
  // Remove the previously plotted region if any
  if (ladLayer) {
    map.removeLayer(ladLayer);
  }

  // Filter the geojson based on the selected LAD22NM
  const selectedData = {
    type: "FeatureCollection",
    features: geojsonData.features.filter((feature) =>
      selectedLAD22NM.includes(feature.properties.LAD22NM)
    ),
  };

  ladLayer = L.geoJSON(selectedData, {
    style: style,
    onEachFeature: onEachFeature,
  }).addTo(map);
  map.fitBounds(ladLayer.getBounds()); // Adjust map view to cover the selected region
}

// Apply the color to each feature
function style(feature) {
  return {
    weight: 2,
    color: "blue",
    fillOpacity: 0.1,
  };
}

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
        this.bindPopup(feature.properties.LAD22NM).openPopup();
      },
      mouseout: function (e) {
        if (ladLayer !== e.target) {
          e.target.setStyle(style(feature)); // Reset to original style
        }
      },
      click: function (e) {
        // Reset style of the previously selected layer
        if (ladLayer) {
          ladLayer.setStyle(style(ladLayer.feature));
        }

        // Highlight the clicked layer
        ladLayer = e.target;
        ladLayer.setStyle({
          weight: 5,
          color: "gold", // Highlight color
          fillOpacity: 0.7,
        });

        // Update Plotly chart
        let featureList = [];
        featureList.push(feature.properties.LAD22NM); // Adjust this as needed
        plotData(featureList);
      },
    });
  }
}

// Initialize Leaflet map
const map = L.map("map").setView([53, -3], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

// Open modal
document.getElementById("uploadBtn").addEventListener("click", function () {
  document.getElementById("myModal").classList.remove("hidden");
});

// Close modal
document.getElementById("closeModalBtn").addEventListener("click", function () {
  document.getElementById("myModal").classList.add("hidden");
});

// Optionally, close the modal when clicking outside of it
document.getElementById("myModal").addEventListener("click", function (event) {
  if (event.target.classList.contains("modal-bg")) {
    document.getElementById("myModal").classList.add("hidden");
  }
});
