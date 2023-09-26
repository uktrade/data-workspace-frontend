const webpack = require("webpack");
const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');
const BundleTracker = require("webpack-bundle-tracker");

module.exports = merge(common, {
  mode: 'development',
  output: {
    publicPath: 'http://0.0.0.0:3000/js/builds/',
  },
  plugins: [
    new webpack.DefinePlugin({
      "process.env": {
        NODE_ENV: JSON.stringify("development"),
      },
    }),
    new BundleTracker({filename: '../stats/react_apps-stats-hot.json'}),
    new webpack.HotModuleReplacementPlugin(),
  ],
  devServer: {
    hot: true,
    historyApiFallback: true,
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: "all",
    headers: { 'Access-Control-Allow-Origin': '*' },
    client: {
      webSocketURL: 'ws://0.0.0.0:3000/ws',
    },
  }
 });
