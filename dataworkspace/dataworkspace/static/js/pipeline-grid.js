function getDagStatus(dag) {
  if (dag === null) return "unknown";
  if (!dag.enabled) return "paused";
  if (dag.last_run === null) return "waiting"
  if (dag.last_run.state === "failed") return "failed";
  if (dag.last_run.state === "success") return "success";
  return "running";
}

function runAction(url) {
  var form = document.createElement('form');
  form.action = url;
  form.method = "POST";
  form.append(createInputFormField('csrfmiddlewaretoken', getCsrfToken()));
  document.body.append(form);
  form.submit();
  form.remove();
}

function initPipelineGrid(rowData) {
  var gridOptions = {
    enableCellTextSelection: true,
    defaultColDef: {
      resizable: true,
      suppressMenu: false,
      floatingFilter: false,
      filter: "text",
      sortable: true
    },
    columnDefs: [{
      field: "table_name",
      headerName: "Table/Report name",
      cellRenderer: "tableNameRenderer"
    }, {
      field: "type"
    }, {
      field: "status",
      cellRenderer: "statusRenderer"
    }, {
      field: "last_run",
      headerName: "Last Run",
      cellRenderer: "lastRunRenderer"
    }, {
      field: "actions",
      cellRenderer: "actionsRenderer",
    }, {
      field: "created_by",
      headerName: "Created by"
    }, {
      field: "created_at",
      headerName: "Created at",
      filter: null
    }],
    components: {
      tableNameRenderer: function (params) {
        return '<a class="govuk-link" href="' + params.data.edit_url + '">' + params.value + '</a>';
      },
      statusRenderer: function (params) {
        var status = getDagStatus(params.data.dag);
        return status[0].toUpperCase() + status.slice(1);
      },
      lastRunRenderer: function(params) {
        var status = getDagStatus(params.data.dag);
        if (status === "running") {
          return params.data.dag.last_run.start_date;
        }
        if (status === "failed" || status === "success") {
          return params.data.dag.last_run.end_date;
        }
        return "-";
      },
      actionsRenderer: function (params) {
        var actions = "<div>";
        if (getDagStatus(params.data.dag) !== "running") {
          if (params.data.config.refresh_type !== 'never') {
            actions += '<a class="govuk-link action-link" href="' + params.data.run_url + '">Run</a>&nbsp;';
          } else {
            actions += "Run&nbsp;";
          }
        }
        else {
          actions += '<a class="govuk-link action-link" href="' + params.data.stop_url + '">Stop</a>';
        }
        actions += "&nbsp;|&nbsp;";
        actions += '<a class="govuk-link" href="' + params.data.log_url + '">View logs</a>';
        actions += "&nbsp;|&nbsp;";
        actions += '<a class="govuk-link" href="' + params.data.delete_url + '">Delete</a>';
        actions += "</div>";
        return actions;
      }
    },
    rowData: rowData
  }
  document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.querySelector('#pipeline-grid');
    new agGrid.Grid(gridDiv, gridOptions);
    gridOptions.api.refreshCells();
    autoSizeColumns(gridOptions.columnApi);
    var actionButtons = document.getElementsByClassName('action-link');
    for (var i = 0; i < actionButtons.length; i++) {
      actionButtons[i].addEventListener('click', function(e) {
        e.preventDefault();
        runAction(e.currentTarget.getAttribute("href"));
      }, false);
    }
  });
}

window.initPipelineGrid = initPipelineGrid;