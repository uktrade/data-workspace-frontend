import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

// Workaround for hot reload "ignored-module" issue when developing locally.
if (module.hot) module.hot.accept();

ReactDOM.render(
  <App />, document.getElementById('test-app')
);
