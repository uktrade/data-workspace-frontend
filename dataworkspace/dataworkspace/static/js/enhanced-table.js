function initEnhancedTable(className) {
  // Given an html table, convert it to a sortable grid
  var tables = document.getElementsByClassName(className);
  for (var t = 0; t < tables.length; t++) {
    var tableEl = tables[t];
    // Determine the column config from the cells in the <thead>
    var headerEL = tableEl.tHead.rows[0];
    var columnConfig = [];
    for (var i = 0; i < headerEL.cells.length; i++) {
      var headerCell = headerEL.cells[i];
      var config = {
        field: headerCell.innerText,
        headerName: headerCell.innerText,
        sortable: headerCell.dataset.sortable !== undefined,
        cellRenderer: headerCell.dataset.renderer,
        type: headerCell.dataset.columnType,
        width: headerCell.dataset.width,
        maxWidth: headerCell.dataset.maxWidth,
        minWidth: headerCell.dataset.minWidth,
        resizable: headerCell.dataset.resizable !== undefined,
      };

      if (
        headerCell.dataset.renderer === "dateRenderer" ||
        headerCell.dataset.renderer === "dateTimeRenderer"
      ) {
        config.comparator = dateSortComparator;
      }
      if (headerCell.dataset.renderer === "htmlRenderer") {
        config.comparator = htmlSortComparator;
      }
      columnConfig.push(config);
    }

    // Collect the data from the existing table into a list of objects ag-grid can read
    var tableData = [];
    var bodyEl = tableEl.tBodies[0];
    for (var i = 0; i < bodyEl.rows.length; i++) {
      var bodyRow = bodyEl.rows[i];
      var dataRow = {};
      for (var j = 0; j < bodyRow.cells.length; j++) {
        var bodyCell = bodyRow.cells[j];
        dataRow[columnConfig[j].field] = bodyCell.innerHTML.trim();
      }
      tableData.push(dataRow);
    }
    // Delete the rows from the original table as we have everything we need to render the grid
    tableEl.innerHTML = "";

    var gridOptions = {
      enableCellTextSelection: true,
      domLayout: "autoHeight",
      suppressRowHoverHighlight: true,
      onGridReady: function (params) {
        window.onresize = function () {
          tableResize(tableEl, params.api);
        };
        tableResize(tableEl, params.api);
      },
      defaultColDef: {
        resizable: true,
        unSortIcon: true,
        headerComponentParams: {
          // We need a custom template as we have custom icons for asc/desc/none sort
          template:
            '<div class="ag-cell-label-container" role="presentation">' +
            '  <span ref="eMenu" class="ag-header-icon ag-header-cell-menu-button"></span>' +
            '  <div ref="eLabel" class="ag-header-cell-label" role="presentation">' +
            '    <div class="header-wrap">' +
            "      <button>" +
            '        <span ref="eText" class="ag-header-cell-text" role="columnheader"></span>' +
            '        <span ref="eSortAsc" class="sort-asc"></span>' +
            '        <span ref="eSortDesc" class="sort-desc"></span>' +
            '        <span ref="eSortNone" class="sort-none"></span>' +
            "      </button>" +
            '      <span ref="eFilter" class="ag-header-icon ag-filter-icon"></span>' +
            "    </div>" +
            "  </div>" +
            "</div>",
        },
      },
      columnDefs: columnConfig,
      rowData: tableData,
      components: {
        htmlRenderer: function (params) {
          return params.value;
        },
        dateRenderer: function (params) {
          return params.value ? dayjs(params.value).format("DD/MM/YYYY") : null;
        },
        datetimeRenderer: function (params) {
          return params.value
            ? dayjs(params.value).format("DD/MM/YYYY H:mm a")
            : null;
        },
      },
    };
    var gridEl = document.createElement("div");
    gridEl.className = "ag-theme-alpine enhanced-table-container";
    tableEl.parentNode.insertBefore(gridEl, tableEl);
    new agGrid.Grid(gridEl, gridOptions);
  }
}
window.initEnhancedTable = initEnhancedTable;
