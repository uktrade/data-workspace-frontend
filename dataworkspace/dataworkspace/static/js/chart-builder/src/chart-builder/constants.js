export const availableCharts = {
  traces: _ => [
    {
      value: 'scatter',
      icon: 'scatter',
      label: 'Scatter',
    }, {
      value: 'line',
      label: 'Line',
    }, {
      value: 'area',
      label: 'Area',
    }, {
      value: 'bar',
      label: 'Bar',
    }, {
      value: 'pie',
      label: 'Pie',
    }, {
      value: 'scattermapbox',
      label: 'Map',
    },
  ],
  complex: true,
}

export const queryStates = {
  running: 0,
  failed: 1,
  complete: 2,
}

export const axisMap = {
  scatter: {
    x: 'x',
    y: 'y',
    xsrc: 'xsrc',
    ysrc: 'ysrc',
  },
  line: {
    x: 'x',
    y: 'y',
    xsrc: 'xsrc',
    ysrc: 'ysrc',
  },
  bar: {
    x: 'x',
    y: 'y',
    xsrc: 'xsrc',
    ysrc: 'ysrc',
  },
  pie: {
    x: 'x',
    y: 'y',
    xsrc: 'labelsrc',
    ysrc: 'valuesrc',
  },
  scattermapbox: {
    x: 'lat',
    y: 'lon',
    xsrc: 'latsrc',
    ysrc: 'lonsrc',
  },
}
