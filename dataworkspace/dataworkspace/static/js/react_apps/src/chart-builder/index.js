import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

// Workaround for hot reload "ignored-module" issue when developing locally.
if (module.hot) {
  module.hot.accept();
}

const el = document.getElementById('chart-builder-app')
ReactDOM.render(
  <App
    chartId={el.attributes['data-chart-id'].value}
    backLink={el.attributes['data-back-link'].value}
    chartData={JSON.parse(document.getElementById('chartConfig').textContent)}
  />, el
);
