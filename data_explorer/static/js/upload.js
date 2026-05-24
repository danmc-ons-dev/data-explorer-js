// 
//fetch("/get_last_upload")
//  .then((response) => response.json())
//  .then((data) => {
//    data = JSON.parse(data.last_upload);
//    PlotlyChart();
 // });

 
function DoCheckUncheckDisplay(d,dchecked)
{
   if( d.checked == true )
   {
      document.getElementById(dchecked).style.display = "block";
      
   }
   else
   {
      document.getElementById(dchecked).style.display = "none";
     
   }
}


// Get columns for dropdown from uploaded CSV
function populateDropdownWithCSV(file) {
  Papa.parse(file, {
    complete: function (results) {
      console.log("Parsed CSV results:", results);

      let columns = results.data[0];
      console.log("Detected columns:", columns);

      let xDropdown = document.getElementById("exposureCol");
      let yDropdown = document.getElementById("outcomeCol");
      let subgeoDropdown = document.getElementById("subgeoCol");
      let subgeotypeDropdown = document.getElementById("subgeotypeCol");
      let lowerDropdown = document.getElementById("lowerCol");
      let higherDropdown = document.getElementById("higherCol");
      let sexDropdown = document.getElementById("sexCol");
      let ageDropdown = document.getElementById("ageCol");
      let socioDropdown = document.getElementById("socioCol");
      let urbanDropdown = document.getElementById("urbanCol");
     
      xDropdown.innerHTML = '<option value="">No column selected</option>';
      yDropdown.innerHTML = '<option value="">No column selected</option>';
      subgeoDropdown.innerHTML = '<option value="">No column selected</option>';
      subgeotypeDropdown.innerHTML = '<option value="">No column selected</option>';
      lowerDropdown.innerHTML = '<option value="">No column selected</option>';
      higherDropdown.innerHTML = '<option value="">No column selected</option>';
      sexDropdown.innerHTML = '<option value="">No column selected</option>';
      ageDropdown.innerHTML = '<option value="">No column selected</option>';
      socioDropdown.innerHTML = '<option value="">No column selected</option>';
      urbanDropdown.innerHTML = '<option value="">No column selected</option>';
     

      columns.forEach((column) => {
        let xOption = document.createElement("option");
        let yOption = document.createElement("option");
        let subgeoOption = document.createElement("option");
        let subgeotypeOption = document.createElement("option");
        let lowerOption = document.createElement("option");
        let higherOption = document.createElement("option");
        let sexOption = document.createElement("option");
        let ageOption = document.createElement("option");
        let socioOption = document.createElement("option");
        let urbanOption = document.createElement("option");
       

        xOption.value = column;
        xOption.text = column;

        yOption.value = column;
        yOption.text = column;

        subgeoOption.value = column;
        subgeoOption.text = column;

        subgeotypeOption.value = column;
        subgeotypeOption.text = column;

        lowerOption.value = column;
        lowerOption.text = column;

        higherOption.value = column;
        higherOption.text = column;

        sexOption.value = column;
        sexOption.text = column;

        ageOption.value = column;
        ageOption.text = column;

        socioOption.value = column;
        socioOption.text = column;

        urbanOption.value = column;
        urbanOption.text = column;


        xDropdown.add(xOption);
        yDropdown.add(yOption);
        subgeoDropdown.add(subgeoOption);
        subgeotypeDropdown.add(subgeotypeOption);
        lowerDropdown.add(lowerOption);
        higherDropdown.add(higherOption);
        sexDropdown.add(sexOption);
        ageDropdown.add(ageOption);
        socioDropdown.add(socioOption);
        urbanDropdown.add(urbanOption);
      
      });
    },
  });
}

// Plot selected columns from dropdown
function plotSelectedColumns() {
  let csvInput = document.getElementById("csvInput");
  let xColumn = document.getElementById("exposureCol").value;
  let yColumn = document.getElementById("outcomeCol").value;
  let groupColumn = document.getElementById("groupColumnPlot").value;
  let plotDisplay = document.getElementById("plotDisplay");

  console.log("Selected columns:", xColumn, yColumn);

  Papa.parse(csvInput.files[0], {
    complete: function (results) {
      let data = results.data;

      let groupedData = {};

      data.slice(1).forEach((row) => {
        let xValue = row[data[0].indexOf(xColumn)];
        let yValue = row[data[0].indexOf(yColumn)];
        let groupValue = groupColumn
          ? row[data[0].indexOf(groupColumn)]
          : "All Data";

        if (!groupedData[groupValue]) {
          groupedData[groupValue] = { x: [], y: [] };
        }

        groupedData[groupValue].x.push(xValue);
        groupedData[groupValue].y.push(yValue);
      });

      let traces = [];
      for (let group in groupedData) {
        traces.push({
          x: groupedData[group].x,
          y: groupedData[group].y,
          name: group,
          type: "scatter",
        });
      }

      Plotly.newPlot(plotDisplay, traces);
    },
  });
}

// Populate dropdown with countries in geojson
function populateDropdown(geojsonData) {
  let dropdown = document.getElementById("country");

  geojsonData.features.forEach((feature) => {
    let option = document.createElement("option");
    option.value = feature.properties.COUNTRY;
    option.textContent = feature.properties.COUNTRY;
    dropdown.appendChild(option);
  });
}

// Load geojson and get countries for dropdown
function populateDropdownWithGJSON() {
  fetch("/static/data/shp/countries_incl_uk.geojson")
    .then((response) => response.json())
    .then((data) => {
      populateDropdown(data);
    })
    .catch((error) => console.error("Error fetching the GeoJSON:", error));
}

// Load map and geojson when page loads
document.addEventListener("DOMContentLoaded", function () {
  populateDropdownWithGJSON();
});

// Upload CSV when selected from input
document.getElementById("csvInput").addEventListener("change", function (e) {
  populateDropdownWithCSV(e.target.files[0]);
});

// Upload modal
/* document.getElementById("uploadBtn").addEventListener("click", function () {
  document.getElementById("myModal").classList.remove("hidden");
}); */

// Upload modal
/* document.getElementById("closeModalBtn").addEventListener("click", function () {
  document.getElementById("myModal").classList.add("hidden");
}); */

// Close the modal when clicking outside of it
/* document.getElementById("myModal").addEventListener("click", function (event) {
  if (event.target.classList.contains("modal-bg")) {
    document.getElementById("myModal").classList.add("hidden");
  }
}); */

// preview data
function previewData(file) {
  Papa.parse(file, {
    complete: function (previewCSV) {
      document.getElementById('previewTable').innerHTML = ''
      //console.log("Parsed preview CSV:", previewCSV);
      const data = previewCSV.data
      //console.log("data:", data);

      var table = document.createElement('table');
      //console.log("table", table);
      var tableBody = document.createElement('tbody');
      //console.log("tableBody", tableBody);

      subset = data.slice(0, 6);
      //console.log("dataslice", data);

      subset.forEach(function (rowData) {
        var row = document.createElement('tr');
       
        rowData.forEach(function (cellData) {
          var cell = document.createElement('td');
          
          cell.appendChild(document.createTextNode(cellData));
         
          row.appendChild(cell);
    
        });
    
        tableBody.appendChild(row);
        //console.log("tablebodyappend", tableBody);
    
      });
  
      table.appendChild(tableBody);
      //console.log("tableappend", table);
      //t = document.getElementById('previewTable');
      document.getElementById('previewTable').appendChild(table);
      //t.appendChild(table);
  
    }
  })

};


document.getElementById("csvInput").addEventListener("change", function (e) {
  document.getElementById("tableDiv").style.display = "block";
    previewData(e.target.files[0]);
  });

