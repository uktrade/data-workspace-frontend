import React from "react";
import "./App.scss";

import { Header } from "./Header";
import { FileList } from "./FileList";
import { BigDataMessage } from "./BigDataMessage";
import { getBreadcrumbs, getFolderName } from "./utils";
import { AddFolderPopup, UploadFilesPopup } from "./popups";
import { DeleteObjectsPopup } from "./popups/DeleteObjects";
import { ErrorModal } from "./components/ErrorModal";

const popupTypes = {
  ADD_FOLDER: "addFolder",
  UPLOAD_FILES: "uploadFiles",
  DELETE_OBJECTS: "deleteObjects",
};

export default class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      files: [],
      folders: [],
      selectedFiles: [],
      filesToDelete: [],
      foldersToDelete: [],
      canDelete: false,
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
      popups: {},
    };

    for (const [key, value] of Object.entries(popupTypes)) {
      this.state.popups[value] = false;
    }

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
    console.log("onfilechange", event.target.files);
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

  onBreadcrumbClick = async (breadcrumb) => {
    console.log(breadcrumb);
    await this.navigateTo(breadcrumb.prefix);
  };

  onRefreshClick = async () => {
    await this.navigateTo(this.state.prefix);
  };

  showNewFolderPopup = async (prefix) => {
    console.log("new folder", prefix);
    this.showPopup(popupTypes.ADD_FOLDER);
  };

  showPopup(popupName) {
    const state = { popups: {} };
    state.popups[popupName] = true;
    this.setState(state);
  }

  hidePopup = (popupName) => {
    console.log("hide", popupName);
    const state = { popups: {} };
    state.popups[popupName] = false;
    this.setState(state);
  };

  onUploadsComplete = async () => {
    console.log("uploads are complete");
    await this.refresh(this.state.currentPrefix);
  };

  createNewFolder = async (prefix, folderName) => {
    console.log("createNewFolderClick");
    console.log(prefix, folderName);
    this.hidePopup(popupTypes.ADD_FOLDER);
    try {
      await this.props.proxy.createFolder(prefix, folderName);
      await this.refresh(prefix);
    }
    catch (ex) {
      this.showErrorPopup(ex);
    }
  };

  onUploadClick = async (prefix) => {
    console.log("upload files to", prefix);
    // this opens the file input ... processing continues
    // in the onFileChange function
    this.fileInputRef.current.click();
  };

  onDeleteClick = async () => {
    console.log("delete click");
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
    const newState = {error, popups: this.state.popups};
    Object.keys(newState.popups).forEach(key => {
      newState.popups[key] = false;
    });
    this.setState(newState)
  }

  handleFileClick = async (key) => {
    console.log("handleFileClick", key);
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
      this.showErrorPopup(ex);
    }
  };

  async navigateTo(prefix) {
    this.setState({ prefix: prefix });
    await this.refresh(prefix);
  }

  handleFolderClick = async (prefix) => {
    console.log("handleFolderClick", prefix);
    await this.navigateTo(prefix);
  };

  async refresh(prefix) {
    const params = {
      Bucket: this.state.bucketName,
      Prefix: prefix || this.state.prefix,
      Delimiter: "/",
    };

    console.log("refresh", params);

    const showBigDataMessage =
      params.Prefix === this.state.rootPrefix + this.state.bigDataFolder;

    try {
      const data = await this.props.proxy.listObjects(params);
        this.setState({
        files: data.files,
        folders: data.folders,
        currentPrefix: params.Prefix,
        showBigDataMessage,
      });
    } catch (ex) {
      this.showErrorPopup(ex);
      return;
    }
  }

  onFileSelect = (file, isSelected) => {
    console.log(file, isSelected);
    let selectedCount = 0;
    this.setState((state) => {
      const files = state.files.map((f) => {
        if (f.Key === file.Key) {
          f.isSelected = isSelected;
        }
        if (f.isSelected) selectedCount++;
        return f;
      });
      state.folders.forEach((f) => {
        if (f.isSelected) selectedCount++;
      });
      return { files, canDelete: selectedCount > 0 };
    });
  };

  onFolderSelect = (folder, isSelected) => {
    let selectedCount = 0;
    this.setState((state) => {
      const folders = state.folders.map((f) => {
        if (f.Prefix === folder.Prefix) {
          f.isSelected = isSelected;
        }
        if (f.isSelected) selectedCount++;
        return f;
      });

      state.files.forEach((f) => {
        if (f.isSelected) selectedCount++;
      });

      return { folders, canDelete: selectedCount > 0 };
    });
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
          style={{ visibility: "hidden" }}
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
            onCancel={() => this.hidePopup(popupTypes.DELETE_OBJECTS)}
            deleter={this.props.deleter}
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
            uploader={this.props.uploader}
          />
        ) : null}

        <Header
          breadCrumbs={breadCrumbs}
          canDelete={this.state.canDelete}
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
    );
  }
}
