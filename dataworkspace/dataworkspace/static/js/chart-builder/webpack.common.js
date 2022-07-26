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
    test_app: [
      path.join(__dirname, './src/test-app/index')
    ]
  },
  output: {
    path: path.resolve('../bundles/'),
    filename: "[name].js",
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
    ],
  },
  optimization: {
    minimize: true,
  },
};
