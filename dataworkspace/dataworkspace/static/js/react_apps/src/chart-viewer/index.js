import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

// Workaround for hot reload "ignored-module" issue when developing locally.
if (module.hot) {
  module.hot.accept();
}

const el = document.getElementById('chart-viewer-app')
ReactDOM.render(
  <App
    datasetId={el.attributes['data-dataset-id'].value}
    chartId={el.attributes['data-chart-id'].value}
    chartData={JSON.parse(document.getElementById('chartConfig').textContent)}
  />, el
);
