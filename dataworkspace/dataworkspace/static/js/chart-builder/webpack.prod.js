const webpack = require("webpack");
const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');
const BundleTracker = require("webpack-bundle-tracker");

module.exports = merge(common, {
  mode: 'production',
  output: {
    publicPath: '/__django_static/js/bundles/',
  },
  plugins: [
    new webpack.DefinePlugin({
      "process.env": {
        NODE_ENV: JSON.stringify("production"),
      },
    }),
    new BundleTracker({filename: '../stats/chart-builder-stats.json'}),
  ],
 });
