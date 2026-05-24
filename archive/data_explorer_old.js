// Pop-up boxes when mouse goes over shapefiles
function onEachFeature(feature, layer) {
  if (feature.properties && feature.properties.COUNTRY) {
    layer.on({
      mouseover: function (e) {
        const layer = e.target;
        layer.setStyle({
          weight: 5, // Highlight the border
          color: "gray",
          fillOpacity: 0.5,
        });
        if (!L.Browser.ie && !L.Browser.opera) {
          layer.bringToFront();
        }
        layer.bindPopup(feature.properties.COUNTRY).openPopup(); // Show popup with the name property
      },
      mouseout: function (e) {
        geojsonLayer.resetStyle(e.target); // Reset style after mouse out
      },
      click: function (e) {
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
      },
    });
  }
}

// Colour shapefiles by attribute
function getColorForProperty(value) {
  // For the sake of simplicity, let's assume value is a number and we color based on a range
  if (value > 50) return "red";
  if (value > 25) return "yellow";
  return "green";
}

// Update colours
function updateColors(property) {
  geojsonLayer.eachLayer(function (layer) {
    const propertyValue = layer.feature.properties[property];
    const color = getColorForProperty(propertyValue);
    layer.setStyle({
      fillColor: color,
    });
  });
}

// Load map and shapefile when page is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Centre on a latitude and longitude and set the zoom level
  const map = L.map("map").setView([51.5, 0], 3);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  fetch("data/countries.geojson")
    .then((response) => response.json())
    .then((data) => {
      // Extract properties from the first feature
      const properties = data.features[0].properties;

      const dropdown = document.getElementById("indicatorSelector");

      for (let prop in properties) {
        const option = document.createElement("option");
        option.value = prop;
        option.textContent = prop.charAt(0).toUpperCase() + prop.slice(1); // Capitalize the property name
        dropdown.appendChild(option);
      }

      geojsonLayer = L.geoJSON(data, {
        style: {
          fillColor: "gray",
          weight: 2,
          opacity: 1,
          color: "white",
          fillOpacity: 0.2,
        },
        onEachFeature: onEachFeature,
      }).addTo(map);
    });
  map.invalidateSize();
});

// Change shapefile colour
document
  .getElementById("indicatorSelector")
  .addEventListener("change", function (e) {
    const selectedProperty = e.target.value;
    updateColors(selectedProperty);
  });
