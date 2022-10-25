const path = require("path");

module.exports = {
  context: __dirname,
  entry: {
    builder: [
      path.join(__dirname, './src/chart-builder/index')
    ],
    viewer: [
      path.join(__dirname, './src/chart-viewer/index')
    ],
    yourfiles: [
      path.join(__dirname, './src/your-files/index')
    ],
  },
  output: {
    path: path.resolve('../bundles/'),
    filename: "[name].[contenthash].js",
  },
  module: {
    rules: [
      {
        test: /\.js|\.jsx$/,
        exclude: /node_modules/,
        use: "babel-loader",
        resolve: {
          extensions: ['.jsx', '.js']
        }
      },
      {
        test: /\.css$/,
        use: ["style-loader", "css-loader"],
      },
      {
        test: /\.s[ac]ss$/i,
        use: [
          // Creates `style` nodes from JS strings
          "style-loader",
          // Translates CSS into CommonJS
          "css-loader",
          // Compiles Sass to CSS
          "sass-loader",
        ],
      },
    ],
  },
  optimization: {
    minimize: true,
  },
};
