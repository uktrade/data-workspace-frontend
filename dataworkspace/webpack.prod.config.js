var webpack = require('webpack')
var BundleTracker = require('webpack-bundle-tracker')

var config = require('./webpack.base.config.js')

// Extend production webpack config here
config.mode = 'production';

config.optimization = {
  minimize: true
}

config.plugins = config.plugins.concat([
  new BundleTracker({path: __dirname, filename: './webpack-stats-prod.json'}),

  // Set node env variable
  new webpack.DefinePlugin({
    'process.env': {
      'NODE_ENV': JSON.stringify('production')
  }}),

  // keeps hashes consistent between compilations
  new webpack.optimize.OccurrenceOrderPlugin(),
])

config.performance = {
  hints: false
}

module.exports = config
