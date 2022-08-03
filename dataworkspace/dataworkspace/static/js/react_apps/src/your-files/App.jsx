import React from "react";
import "./App.css";

import { Header } from "./Header";
import { FileList } from "./FileList";
import { BigDataMessage } from "./BigDataMessage";
import { getBreadcrumbs } from "./utils";
import { AddFolderPopup } from "./Popups";

const popupTypes = {
  ADD_FOLDER: "addFolder",
};

export default class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      files: [],
      folders: [],
      currentPrefix: this.props.config.rootPrefix,
      bigDataFolder: this.props.config.bigdataPrefix,
      isLoaded: false,
      error: null,
      bucketName: this.props.config.bucketName,
      prefix: this.props.config.initialPrefix,
      rootPrefix: this.props.config.initialPrefix,
      region: this.props.config.region,
      showBigDataMessage: false,
      popups: {},
    };

    for (const [key, value] of Object.entries(popupTypes)) {
      this.state.popups[value] = false;
    }

    this.handleFileClick = this.handleFileClick.bind(this);
    this.handleFolderClick = this.handleFolderClick.bind(this);

    this.handleBreadcrumbClick = this.handleBreadcrumbClick.bind(this);
    this.handleRefreshClick = this.handleRefreshClick.bind(this);
    this.handleCreateTableClick = this.handleCreateTableClick.bind(this);

    this.showNewFolderPopup = this.showNewFolderPopup.bind(this);
    this.createNewFolderClick = this.createNewFolderClick.bind(this);
    this.hidePopup = this.hidePopup.bind(this);
  }

  async componentDidMount() {
    console.log("componentDidMount");
    await this.refresh();
  }

  async handleCreateTableClick(key) {
    console.log("create table", key);
  }

  async handleBreadcrumbClick(breadcrumb) {
    console.log(breadcrumb);
    await this.navigateTo(breadcrumb.prefix);
  }

  async handleRefreshClick() {
    await this.navigateTo(this.state.prefix);
  }

  async showNewFolderPopup(prefix) {
    console.log("new folder", prefix);
    this.showPopup(popupTypes.ADD_FOLDER);
  }

  showPopup(popupName) {
    const state = { popups: {} };
    state.popups[popupName] = true;
    this.setState(state);
  }

  hidePopup(popupName) {
    console.log("hide", popupName);
    const state = { popups: {} };
    state.popups[popupName] = false;
    this.setState(state);
  }

  async createNewFolderClick(prefix, folderName) {
    console.log("createNewFolderClick");
    console.log(prefix, folderName);
    this.hidePopup(popupTypes.ADD_FOLDER);
    await this.props.proxy.createFolder(prefix, folderName);
    await this.refresh(prefix);
  }

  async handleUploadClick(prefix) {
    console.log("upload files to", prefix);
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
    await this.navigateTo(prefix);
  }

  async refresh(prefix) {
    const params = {
      Bucket: this.state.bucketName,
      Prefix: prefix || this.state.prefix,
      Delimiter: "/",
    };

    console.log("refresh", params);

    const showBigDataMessage =
      params.Prefix === this.state.rootPrefix + this.state.bigDataFolder;

    const data = await this.props.proxy.listObjects(params);

    console.log(data);
    this.setState({
      files: data.files,
      folders: data.folders,
      currentPrefix: params.Prefix,
      showBigDataMessage,
    });
  }

  render() {
    const breadCrumbs = getBreadcrumbs(
      this.state.rootPrefix,
      this.state.prefix
    );

    const currentPrefix = this.state.currentPrefix;

    return (
      <div className="browser">
        {this.state.popups.addFolder ? (
          <AddFolderPopup
            currentPrefix={currentPrefix}
            onSuccess={this.createNewFolderClick}
            onCancel={() => this.hidePopup("addFolder")}
          />
        ) : null}

        <Header
          breadCrumbs={breadCrumbs}
          currentPrefix={currentPrefix}
          onBreadcrumbClick={this.handleBreadcrumbClick}
          onRefreshClick={this.handleRefreshClick}
          onNewFolderClick={this.showNewFolderPopup}
          onUploadClick={this.handleUploadClick}
          onDeleteClick={this.handleDeleteClick}
        />
        <FileList
          files={this.state.files}
          folders={this.state.folders}
          onFileClick={this.handleFileClick}
          onFolderClick={this.handleFolderClick}
          onCreateTableClick={this.handleCreateTableClick}
        />
        {this.state.showBigDataMessage ? (
          <BigDataMessage
            bigDataFolder={this.state.bigDataFolder}
            bucketName={this.state.bucketName}
          />
        ) : null}
      </div>
    );
  }
}
