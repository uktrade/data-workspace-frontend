document.addEventListener("DOMContentLoaded", () => {
  const columnDefs = JSON.parse(
    document.getElementById("column_data").textContent
  );
  const instanceDetails = JSON.parse(
    document.getElementById("instance_details").textContent
  );

  columnDefs.push({
    field: "actions",
    filter: false,
    sortable: false,
    cellRenderer: function (cellData) {
      var editButton = document.createElement("a");
      editButton.href =
        `/admin/app/referencedata/${instanceDetails.id}/data/` +
        cellData.data._id +
        "/change/";
      editButton.title = "Edit this record";
      editButton.type = "button";
      editButton.className = "button";
      editButton.innerHTML = "Edit record";
      return editButton;
    },
  });

  const gridDiv = document.querySelector("#data-grid");
  const gridOptions = {
    suppressMenuHide: true,
    enableCellTextSelection: true,
    defaultColDef: {
      resizable: true,
      filterParams: {
        buttons: ["reset"],
      },
    },
    columnDefs: columnDefs,
    rowData: [],
  };

  new agGrid.Grid(gridDiv, gridOptions);
  gridOptions.api.showLoadingOverlay();

  var xhr = new XMLHttpRequest();
  xhr.open("GET", instanceDetails.url, true);
  xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
  xhr.onreadystatechange = function () {
    if (this.readyState === XMLHttpRequest.DONE) {
      if (this.status === 200) {
        gridOptions.api.setRowData(JSON.parse(xhr.responseText).records);
        autoSizeColumns(gridOptions.columnApi);
      } else {
        gridOptions.overlayNoRowsTemplate =
          this.status === 504
            ? "<p>The data you requested has taken too long to load. Please try again or contact the <a href='https://data.trade.gov.uk/support-and-feedback/'> Data Workspace team</a> if the problem continues.</p>"
            : "<p>An unknown error occurred</p>";
        gridOptions.api.showNoRowsOverlay();
      }
    }
  };
  xhr.send();
});
