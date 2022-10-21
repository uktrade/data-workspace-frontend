import React from "react";
import "./App.scss";

import { Uploader } from "./uploader";
import { S3Proxy } from "./s3-proxy";
import { S3Deleter } from "./s3-deleter";

import { Header } from "./Header";
import { FileList } from "./FileList";
import { BigDataMessage } from "./BigDataMessage";
import { getBreadcrumbs, getFolderName } from "./utils";
import { AddFolderPopup, UploadFilesPopup } from "./popups";
import { DeleteObjectsPopup } from "./popups/DeleteObjects";
import { ErrorModal } from "./popups/ErrorModal";

const popupTypes = {
  ADD_FOLDER: "addFolder",
  UPLOAD_FILES: "uploadFiles",
  DELETE_OBJECTS: "deleteObjects",
};

export default class App extends React.Component {
  constructor(props) {
    super(props);

    this.proxy = new S3Proxy(this.props.config);
    this.uploader = new Uploader(this.proxy, {
      bucketName: this.props.config.bucketName,
    });
    this.deleter = new S3Deleter(this.proxy, this.props.config.bucketName);

    this.state = {
      files: [],
      folders: [],
      selectedFiles: [],
      filesToDelete: [],
      foldersToDelete: [],
      currentPrefix: this.props.config.rootPrefix,
      bigDataFolder: this.props.config.bigdataPrefix,
      createTableUrl: this.props.config.createTableUrl,
      isLoaded: false,
      error: null,
      bucketName: this.props.config.bucketName,
      prefix: this.props.config.initialPrefix,
      rootPrefix: this.props.config.initialPrefix,
      region: this.props.config.region,
      showBigDataMessage: false,
      popups: Object.fromEntries(Object.entries(popupTypes).map((key, value) => [value, false])),
      dragActive: false,
    };

    this.fileInputRef = React.createRef();
  }

  createFilesArrayFromFileList(filelist) {
    const files = [];

    for (let i = 0; i < filelist.length; i++) {
      const file = filelist[i];
      file.relativePath = file.name;
      files.push(file);
    }

    return files;
  }

  async componentDidMount() {
    await this.refresh();
  }

  onFileChange = (event) => {
    if (!event.target.files) {
      console.log("nothing selected");
      return;
    }
    const files = this.createFilesArrayFromFileList(event.target.files);
    this.setState({
      selectedFiles: files,
    });
    this.showPopup(popupTypes.UPLOAD_FILES);
  };

  onBreadcrumbClick = async (e, breadcrumb) => {
    e.preventDefault();
    await this.navigateTo(breadcrumb.prefix);
  };

  onRefreshClick = async () => {
    await this.navigateTo(this.state.prefix);
  };

  showNewFolderPopup = async (prefix) => {
    this.showPopup(popupTypes.ADD_FOLDER);
  };

  showPopup(popupName) {
    const state = { popups: {} };
    state.popups[popupName] = true;
    this.setState(state);
  }

  hidePopup = (popupName) => {
    const state = { popups: {} };
    state.popups[popupName] = false;
    this.setState(state);
  };

  onUploadsComplete = async () => {
    await this.refresh(this.state.currentPrefix);
  };

  createNewFolder = async (prefix, folderName) => {
    this.hidePopup(popupTypes.ADD_FOLDER);
    try {
      await this.proxy.createFolder(prefix, folderName);
      await this.refresh(prefix);
    } catch (ex) {
      this.showErrorPopup(ex);
    }
  };

  onUploadClick = async (prefix) => {
    // this opens the file input ... processing continues
    // in the onFileChange function
    this.fileInputRef.current.click();
  };

  onDeleteClick = async () => {
    const filesToDelete = this.state.files.filter((file) => {
      return file.isSelected;
    });

    const foldersToDelete = this.state.folders.filter((folder) => {
      return folder.isSelected;
    });

    console.log(
      `delete ${filesToDelete.length} files and ${foldersToDelete.length} folders`
    );

    this.setState({
      filesToDelete,
      foldersToDelete,
    });

    this.showPopup(popupTypes.DELETE_OBJECTS);
  };

  showErrorPopup = (error) => {
    const newState = { error, popups: this.state.popups };
    Object.keys(newState.popups).forEach((key) => {
      newState.popups[key] = false;
    });
    this.setState(newState);
  };

  handleFileClick = async (key) => {
    const params = {
      Bucket: this.state.bucketName,
      Key: key,
      Expires: 15,
      ResponseContentDisposition: "attachment",
    };

    let url;
    try {
      url = await this.proxy.getSignedUrl(params);
      console.log(url);
      window.location.href = url;
    } catch (ex) {
      this.showErrorPopup(ex);
    }
  };

  async navigateTo(prefix) {
    this.setState({ prefix: prefix });
    await this.refresh(prefix);
  }

  handleFolderClick = async (prefix) => {
    await this.navigateTo(prefix);
  };

  async refresh(prefix) {
    const params = {
      Bucket: this.state.bucketName,
      Prefix: prefix || this.state.prefix,
      Delimiter: "/",
    };

    const showBigDataMessage =
      params.Prefix === this.state.rootPrefix + this.state.bigDataFolder;

    try {
      const data = await this.proxy.listObjects(params);
      this.setState({
        files: data.files,
        folders: data.folders,
        currentPrefix: params.Prefix,
        showBigDataMessage,
      });
    } catch (ex) {
      this.showErrorPopup(ex);
    }
  }

  onFileSelect = (file, isSelected) => {
    this.setState({
      files: this.state.files.map((f) => {
        if (f.Key === file.Key) {
          f.isSelected = isSelected;
        }
        return f;
      }),
    });
  };

  onFolderSelect = (folder, isSelected) => {
    this.setState({
      folders: this.state.folders.map((f) => {
        if (f.Prefix === folder.Prefix) {
          f.isSelected = isSelected;
        }
        return f;
      }),
    });
  };

  handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({ dragActive: true });
  };

  handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Don't fire the leave event if we are dragging over a child element
    if (e.currentTarget.contains(e.relatedTarget)) return;
    this.setState({ dragActive: false });
  };

  handleDragOver = (e) => {
    // We need to cancel the drag over event to allow the drop event
    // to be picked up on a child element
    e.preventDefault();
    e.stopPropagation();
  };

  handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    this.setState({
      dragActive: false,
      selectedFiles: this.createFilesArrayFromFileList(e.dataTransfer.files),
    });
    this.showPopup(popupTypes.UPLOAD_FILES);
  };

  render() {
    const breadCrumbs = getBreadcrumbs(
      this.state.rootPrefix,
      this.state.prefix
    );

    const currentFolderName = getFolderName(
      this.state.currentPrefix,
      this.state.rootPrefix
    );

    return (
      <div className="browser">
        <input
          type="file"
          onChange={this.onFileChange}
          multiple={true}
          ref={this.fileInputRef}
          style={{ display: "none" }}
        />
        {this.state.error ? (
          <ErrorModal
            error={this.state.error}
            onClose={() => this.setState({ error: null })}
          />
        ) : null}
        {this.state.popups.deleteObjects ? (
          <DeleteObjectsPopup
            filesToDelete={this.state.filesToDelete}
            foldersToDelete={this.state.foldersToDelete}
            onClose={async () => {
              this.hidePopup(popupTypes.DELETE_OBJECTS);
            }}
            onSuccess={async () => {
              await this.onRefreshClick();
            }}
            deleter={this.deleter}
          />
        ) : null}
        {this.state.popups.addFolder ? (
          <AddFolderPopup
            currentPrefix={this.state.currentPrefix}
            onSuccess={this.createNewFolder}
            onCancel={() => this.hidePopup(popupTypes.ADD_FOLDER)}
          />
        ) : null}

        {this.state.popups[popupTypes.UPLOAD_FILES] ? (
          <UploadFilesPopup
            currentPrefix={this.state.currentPrefix}
            selectedFiles={this.state.selectedFiles}
            folderName={currentFolderName}
            onCancel={() => this.hidePopup(popupTypes.UPLOAD_FILES)}
            onUploadsComplete={this.onUploadsComplete}
            uploader={this.uploader}
          />
        ) : null}

        <div
          className={`drop-zone ${this.state.dragActive ? "drag-active" : ""}`}
          onDragEnter={this.handleDragEnter}
          onDragLeave={this.handleDragLeave}
          onDrop={this.handleDrop}
          onDragOver={this.handleDragOver}
        >
          <Header
            breadCrumbs={breadCrumbs}
            canDelete={
              this.state.folders
                .concat(this.state.files)
                .filter((f) => f.isSelected).length > 0
            }
            currentPrefix={this.state.currentPrefix}
            onBreadcrumbClick={this.onBreadcrumbClick}
            onRefreshClick={this.onRefreshClick}
            onNewFolderClick={this.showNewFolderPopup}
            onUploadClick={this.onUploadClick}
            onDeleteClick={this.onDeleteClick}
          />
          <FileList
            files={this.state.files}
            folders={this.state.folders}
            createTableUrl={this.state.createTableUrl}
            onFolderClick={this.handleFolderClick}
            onFolderSelect={this.onFolderSelect}
            onFileClick={this.handleFileClick}
            onFileSelect={this.onFileSelect}
          />
          {this.state.showBigDataMessage ? (
            <BigDataMessage
              bigDataFolder={this.state.bigDataFolder}
              bucketName={this.state.bucketName}
            />
          ) : null}
        </div>
      </div>
    );
  }
}
