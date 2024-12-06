/* eslint-disable */
const path = require('path');

const REACT_APPS = [
  'home-page',
  'data-cut',
  'source-dataset',
  'reference-dataset',
  'visualisations',
  'your-files',
  'data-catalogue-feedback',
  'confirm-remove-user'
].reduce(
  (prev, acc) => ({
    ...prev,
    [acc]: path.join(__dirname, `./react/features/${acc}/index`)
  }),
  {}
);

const APPS = ['ckeditor'].reduce(
  (prev, acc) => ({
    ...prev,
    [acc]: path.join(__dirname, `./${acc}/index`)
  }),
  {}
);

module.exports = {
  context: __dirname,
  entry: {...APPS, ...REACT_APPS},
  output: {
    path: path.resolve('./bundles/'),
    filename: '[name].[contenthash].js',
    clean: true
  },
  module: {
    rules: [
      {
        test: /\.js|\.jsx$/,
        exclude: /node_modules/,
        use: 'babel-loader',
        resolve: {
          extensions: ['.jsx', '.js']
        }
      },
      {
        test: /\.ts|\.tsx$/,
        use: 'ts-loader',
        exclude: /node_modules/
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      },
      {
        test: /\.s[ac]ss$/i,
        use: [
          // Creates `style` nodes from JS strings
          'style-loader',
          // Translates CSS into CommonJS
          'css-loader',
          // Compiles Sass to CSS
          'sass-loader'
        ]
      }
    ]
  },
  optimization: {
    minimize: true
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js']
  }
};
