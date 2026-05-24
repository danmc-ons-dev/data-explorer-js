let currentData = null;

document.getElementById('csvInput1').addEventListener('change', function (event) {
    handleCSVUpload(event, '1');
});

document.getElementById('csvInput2').addEventListener('change', function (event) {
    handleCSVUpload(event, '2');
});

function handleCSVUpload(event, plotNumber) {
    Papa.parse(event.target.files[0], {
        complete: function (results) {
            currentData = results.data;

            // Extract column headers for dropdowns
            let headers = currentData[0];

            // Populate the dropdowns
            let xColumnSelect = document.getElementById(`xColumnPlot${plotNumber}`);
            let yColumnSelect = document.getElementById(`yColumnPlot${plotNumber}`);
            xColumnSelect.innerHTML = '';
            yColumnSelect.innerHTML = '';

            headers.forEach(header => {
                let xOption = document.createElement('option');
                xOption.value = header;
                xOption.text = header;
                xColumnSelect.appendChild(xOption);

                let yOption = document.createElement('option');
                yOption.value = header;
                yOption.text = header;
                yColumnSelect.appendChild(yOption.cloneNode(true));
            });
        }
    });
}

function plotSelectedColumns(plotNumber) {
    let xColumnSelect = document.getElementById(`xColumnPlot${plotNumber}`);
    let yColumnSelect = document.getElementById(`yColumnPlot${plotNumber}`);

    let xColumnName = xColumnSelect.value;
    let yColumnName = yColumnSelect.value;

    let xColumnIndex = currentData[0].indexOf(xColumnName);
    let yColumnIndex = currentData[0].indexOf(yColumnName);

    let xData = [];
    let yData = [];

    for (let i = 1; i < currentData.length; i++) {
        xData.push(currentData[i][xColumnIndex]);
        yData.push(currentData[i][yColumnIndex]);
    }

    let plotData = [{
        x: xData,
        y: yData,
        type: 'scatter'
    }];

    Plotly.newPlot(`plot${plotNumber}Display`, plotData);
}
