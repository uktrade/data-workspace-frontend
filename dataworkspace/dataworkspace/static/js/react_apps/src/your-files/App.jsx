import React from "react";
import "./App.css";

import { Header } from "./Header";
import { FileList } from "./FileList";
import { BigDataMessage } from "./BigDataMessage";
import { getBreadcrumbs } from "./utils";

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
      rootPrefix: this.props.config.initialPrefix,
      region: this.props.config.region,
      showBigDataMessage: false,
    };

    this.handleFileClick = this.handleFileClick.bind(this);
    this.handleFolderClick = this.handleFolderClick.bind(this);
    this.handleBreadcrumbClick = this.handleBreadcrumbClick.bind(this);
    this.handleRefreshClick = this.handleRefreshClick.bind(this);
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
    this.setState({ files: data.files, folders: data.folders });
  }

  async componentDidMount() {
    console.log("componentDidMount");
    await this.refresh();
  }

  async handleBreadcrumbClick(breadcrumb) {
    console.log(breadcrumb);
    await this.navigateTo(breadcrumb.prefix);
  }

  async handleRefreshClick() {
    await this.navigateTo(this.state.prefix);
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

  async handleFileClick(key) {
    console.log(key);
    const params = {
      Bucket: this.state.bucketName,
      Key: key,
      Expires: 15,
      ResponseContentDisposition: "attachment",
    };

    let url;
    try {
      url = await this.props.proxy.getSignedUrl(params);
      console.log(url);
      window.location.href = url;
    } catch (ex) {
      logger.error(ex);
    }
  }

  async navigateTo(prefix) {
    this.setState({ prefix: prefix });
    await this.refresh(prefix);
  }

  async handleFolderClick(prefix) {
    console.log("handleFolderClick", arguments);
    // console.log(prefix);
    // const state = { prefix: prefix };
    // const url = prefix + ".html";
    // history.pushState(state, "", url);
    await this.navigateTo(prefix);
  }

  render() {
    const breadCrumbs = getBreadcrumbs(
      this.state.rootPrefix,
      this.state.prefix
    );

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
        <BigDataMessage display={this.state.showBigDataMessage} />
      </div>
    );
  }
}
