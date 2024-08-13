/* eslint-disable */
const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');

const REACT_APPS = [
  'home-page',
  'data-cut',
  'source-dataset',
  'reference-dataset',
  'visualisations',
  'your-files',
  'your-files-v2',
  'data-catalogue-feedback'
].reduce(
  (prev, acc) => ({
    ...prev,
    [acc]: path.join(__dirname, `./react/features/${acc}/index`)
  }),
  {}
);

const APPS = ['tinymce-editor'].reduce(
  (prev, acc) => ({
    ...prev,
    [acc]: path.join(__dirname, `./${acc}/index`)
  }),
  {}
);

module.exports = {
  context: __dirname,
  entry: { ...APPS, ...REACT_APPS },
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
        test: /skin.css$/i,
        use: [MiniCssExtractPlugin.loader, 'css-loader']
      },
      {
        test: /content.css$/i,
        use: ['css-loader']
      },
      {
        test: /FileList.css$/i,
        use: ['css-loader']
      },
      {
        test: /.scss$/,
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
  resolve: {
    extensions: ['.tsx', '.ts', '.js']
  }
};
