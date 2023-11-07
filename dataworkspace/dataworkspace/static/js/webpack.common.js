/* eslint-disable */
const path = require('path');

module.exports = {
  context: __dirname,
  entry: {
    yourfiles: path.join(__dirname, './react/modules/your-files/index'),
    'data-cut': path.join(__dirname, './react/modules/data-cut/index'),
    'source-dataset': path.join(
      __dirname,
      './react/modules/source-dataset/index'
    ),
    'reference-dataset': path.join(
      __dirname,
      './react/modules/reference-dataset/index'
    ),
    visualisations: path.join(__dirname, './react/modules/visualisations/index'),
    'home-page': path.join(
      __dirname,
      './react/modules/home-page/index')
  },
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
