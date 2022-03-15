const webpack = require("webpack");
const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');
const BundleTracker = require("webpack-bundle-tracker");

module.exports = merge(common, {
  mode: 'development',
  entry: {
    builder: [
      'react-hot-loader/patch',
      'webpack-dev-server/client?http://0.0.0.0:3000',
      'webpack/hot/only-dev-server',
    ],
    viewer: [
      'react-hot-loader/patch',
      'webpack-dev-server/client?http://0.0.0.0:3000',
      'webpack/hot/only-dev-server',
    ]
  },
  output: {
    publicPath: 'http://0.0.0.0:3000/js/builds/',
  },
  plugins: [
    new webpack.DefinePlugin({
      "process.env": {
        NODE_ENV: JSON.stringify("development"),
      },
    }),
    new BundleTracker({filename: '../stats/chart-builder-stats-hot.json'}),
    new webpack.HotModuleReplacementPlugin(),
  ],
  devServer: {
    inline: true,
    hot: true,
    historyApiFallback: true,
    host: '0.0.0.0',
    port: 3000,
    disableHostCheck: true,
    headers: { 'Access-Control-Allow-Origin': '*' }
  }
 });
