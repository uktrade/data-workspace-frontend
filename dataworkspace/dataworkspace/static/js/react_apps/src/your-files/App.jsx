import React from "react";
import "./App.scss";

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

class Credentials extends AWS.Credentials {
  constructor(credentialsUrl) {
    super();
    this.expiration = 0;
    this.credentialsUrl = credentialsUrl;
  }

  async refresh(callback) {
    try {
      const response = await (await fetch(this.credentialsUrl)).json();
      this.accessKeyId = response.AccessKeyId;
      this.secretAccessKey = response.SecretAccessKey;
      this.sessionToken = response.SessionToken;
      this.expiration = Date.parse(response.Expiration);
    } catch (err) {
      callback(err);
      return;
    }

    callback();
  }

  needsRefresh() {
    return this.expiration - 60 < Date.now();
  }
}

export default class App extends React.Component {
  constructor(props) {
    super(props);

    const awsConfig = {
      credentials: new Credentials(this.props.config.credentialsUrl),
      region: this.props.config.region,
      s3ForcePathStyle: true,
      ...(this.props.config.endpointUrl ? {endpoint: this.props.config.endpointUrl} : {})
    }
    console.log('AWS Config', awsConfig);
    this.s3 = new AWS.S3(awsConfig);

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

  async componentDidMount() {
    await this.refresh();
  }

  onFileChange = (event) => {
    if (!event.target.files) {
      console.log("nothing selected");
      return;
    }

    const files = [];

    for (let i = 0; i < event.target.files.length; i++) {
      const file = event.target.files[i];
      file.relativePath = file.name;
      files.push(file);
    }

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
      url = await this.s3.getSignedUrlPromise("getObject", params)
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
    const initialPrefix = this.props.config.initialPrefix;
    const bigdataPrefix = this.props.config.bigdataPrefix;
    const showBigDataMessage = prefix === this.state.rootPrefix + this.state.bigDataFolder;
    const params = {
      Bucket: this.state.bucketName,
      Prefix: prefix || this.state.prefix,
      Delimiter: "/",
    };

    const listObjects = async () => {
      const response = await this.s3.listObjectsV2(params).promise();
      const files = response.Contents
        .filter((file) => (file.Key !== params.Prefix))
        .map((file) => ({
          ...file,
          formattedDate: new Date(file.LastModified),
          isSelected: false,
        }));

      const teamsFolders = (params.Prefix === initialPrefix) ? (this.props.config.teamsPrefixes.map((prefix) => ({
        Prefix: prefix,
        isSharedFolder: true,
        isSelected: false,
      }))) : [];

      const bigDataFolder = (params.Prefix === initialPrefix) ? [{
          Prefix: initialPrefix + bigdataPrefix,
          isBigData: true,
          isSelected: false,
        }] : [];

      const foldersWithoutBigData = response.CommonPrefixes.filter((folder) => {
        return folder.Prefix !== `${initialPrefix}${bigdataPrefix}`;
      }).map((folder) => ({
        ...folder,
        isBigData: false,
        isSelected: false,
      }))
      const folders = teamsFolders.concat(bigDataFolder).concat(foldersWithoutBigData);

      return {
        files,
        folders,
      };
    }

    try {
      const data = await listObjects();
      this.setState({
        files: data.files,
        folders: data.folders,
        currentPrefix: params.Prefix,
        showBigDataMessage,
      });
    } catch (ex) {
      this.showErrorPopup(ex);
      return
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

  handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();

    async function entries(directoryReader) {
        var entries = [];
        while (true) {
            var latestEntries = await new Promise((resolve, reject) => {
                directoryReader.readEntries(resolve, reject);
            });
            if (latestEntries.length == 0) break;
            entries = entries.concat(latestEntries);
        }
        return entries;
    }

    async function file(fileEntry) {
        var file = await new Promise((resolve, reject) => {
            fileEntry.file(resolve, reject);
        });
        // We monkey-patch the file to include its FileSystemEntry fullPath,
        // which is a path relative to the root of the pseudo-filesystem of
        // a dropped folder
        file.relativePath = fileEntry.fullPath.substring(1);  // Remove leading slash
        return file;
    }

    async function getFiles(dataTransferItemList) {
        const files = [];
        // DataTransferItemList does not support map
        const fileAndDirectoryEntryQueue = [];
        for (let i = 0; i < dataTransferItemList.length; ++i) {
             // At the time of writing no browser supports `getAsEntry`
            fileAndDirectoryEntryQueue.push(dataTransferItemList[i].webkitGetAsEntry());
        }

        while (fileAndDirectoryEntryQueue.length > 0) {
            const entry = fileAndDirectoryEntryQueue.shift();
            if (entry.isFile) {
                files.push(await file(entry));
            } else if (entry.isDirectory) {
                fileAndDirectoryEntryQueue.push(...await entries(entry.createReader()));
            }
        }
        return files;
    }

    this.setState({
      dragActive: false,
      selectedFiles: await getFiles(e.dataTransfer.items),
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
            s3={this.s3}
            bucketName={this.props.config.bucketName}
            filesToDelete={this.state.filesToDelete}
            foldersToDelete={this.state.foldersToDelete}
            onClose={async () => {
              this.hidePopup(popupTypes.DELETE_OBJECTS);
            }}
            onSuccess={async () => {
              await this.onRefreshClick();
            }}
          />
        ) : null}
        {this.state.popups.addFolder ? (
          <AddFolderPopup
            s3={this.s3}
            bucketName={this.props.config.bucketName}
            currentPrefix={this.state.currentPrefix}
            onSuccess={() => this.onRefreshClick()}
            onClose={() => this.hidePopup(popupTypes.ADD_FOLDER)}
            onError={(ex) => this.showErrorPopup(ex)}
          />
        ) : null}

        {this.state.popups[popupTypes.UPLOAD_FILES] ? (
          <UploadFilesPopup
            s3={this.s3}
            bucketName={this.props.config.bucketName}
            currentPrefix={this.state.currentPrefix}
            selectedFiles={this.state.selectedFiles}
            folderName={currentFolderName}
            onCancel={() => this.hidePopup(popupTypes.UPLOAD_FILES)}
            onUploadsComplete={this.onUploadsComplete}
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
