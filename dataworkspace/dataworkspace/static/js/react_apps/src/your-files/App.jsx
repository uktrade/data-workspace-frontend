import React from "react";
import "./App.css";

import { Header } from "./Header";
import { FileList } from "./FileList";
import { BigDataMessage } from "./BigDataMessage";

export default class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      files: [],
      folders: [],
      isLoaded: false,
      error: null,
      bucketName: this.props.config.bucketName,
      prefix: this.props.config.initialPrefix,
      region: this.props.config.region,
    };

    this.handleFileClick = this.handleFileClick.bind(this);
    this.handleFolderClick = this.handleFolderClick.bind(this);
    this.handleBreadcrumbClick = this.handleBreadcrumbClick.bind(this);
  }

  async refresh(prefix) {
    const params = {
      Bucket: this.state.bucketName,
      Prefix: prefix || this.state.prefix,
      Delimiter: "/",
    };

    console.log("refresh", params);

    const data = await this.props.proxy.listObjects(params);
    console.log(data);
    this.setState({ files: data.Contents, folders: data.CommonPrefixes });
  }

  async componentDidUpdate() {
    console.log("componentDidUpdate");
    // await this.refresh();
  }

  async componentDidMount() {
    console.log("componentDidMount");
    await this.refresh();
  }

  handleBreadcrumbClick() {
    console.log("handleBreadcrumbClick", arguments);
  }

  async handleRefreshClick() {
    console.log("refresh");
  }

  async handleNewFolderClick() {
    console.log("new folder");
  }

  async handleUploadClick() {
    console.log("upload files");
  }

  async handleDeleteClick() {
    console.log("delete click");
  }

  getBreadcrumbs() {
    const prefix = this.state.prefix;
    const data = [
      {
        prefix: prefix,
        label: "home",
      },
    ];

    return data;
  }

  handleFileClick() {
    console.log("handleFileClick", arguments);
  }

  async handleFolderClick(prefix) {
    console.log("handleFolderClick", arguments);
    console.log(prefix);
    this.setState({ prefix: prefix });
    await this.refresh(prefix);
  }

  render() {
    const breadCrumbs = this.getBreadcrumbs();
    return (
      <div className="browser">
        <Header
          breadCrumbs={breadCrumbs}
          onBreadcrumbClick={this.handleBreadcrumbClick}
          onRefreshClick={this.handleRefreshClick}
          onNewFolderClick={this.handleNewFolderClick}
          onUploadClick={this.handleUploadClick}
          onDeleteClick={this.handleDeleteClick}
        />
        <FileList
          files={this.state.files}
          folders={this.state.folders}
          onFileClick={this.handleFileClick}
          onFolderClick={this.handleFolderClick}
        />
        <BigDataMessage />
      </div>
    );
  }
}
