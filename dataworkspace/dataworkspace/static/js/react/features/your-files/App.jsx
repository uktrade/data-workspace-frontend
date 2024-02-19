import React from 'react';
import './App.scss';

import { Header } from './Header';
import { FileList } from './FileList';
import { BigDataMessage } from './BigDataMessage';
import { getBreadcrumbs, getFolderName } from './utils';
import { AddFolderPopup, UploadFilesPopup } from './popups';
import { DeleteObjectsPopup } from './popups/DeleteObjects';
import { ErrorModal } from './popups/ErrorModal';
import { TeamsPrefixMessage } from './TeamsPrefixMessage';

const popupTypes = {
  ADD_FOLDER: 'addFolder',
  UPLOAD_FILES: 'uploadFiles',
  DELETE_OBJECTS: 'deleteObjects'
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
    const appConfig = this.props.config;
    const awsConfig = {
      credentials: new Credentials(appConfig.credentialsUrl),
      region: appConfig.region,
      s3ForcePathStyle: true,
      ...(appConfig.endpointUrl ? { endpoint: appConfig.endpointUrl } : {}),
      httpOptions: {
        // Total time a request is allowed to take, which for a multipart upload
        // is the total time a single 5MB is allowed to take. The default is 2
        // mins, but some people were hitting timeout errors, so bumped it to
        // 10 minutes
        timeout: 10 * 60 * 60 * 1000
      }
    };
    console.log('AWS Config', awsConfig);
    this.s3 = new AWS.S3(awsConfig);

    this.state = {
      files: [],
      folders: [],
      selectedFiles: [],
      filesToDelete: [],
      foldersToDelete: [],
      // Ensure the user provided prefix ends with a slash but does not start with a slash
      currentPrefix: appConfig.initialPrefix
        .replace(/^\//, '')
        .replace(/([^\/]$)/, '$1/'),
      bigDataFolder: appConfig.bigdataPrefix,
      createTableUrl: appConfig.createTableUrl,
      isLoaded: false,
      error: null,
      bucketName: appConfig.bucketName,
      region: appConfig.region,
      showBigDataMessage: false,
      popups: Object.fromEntries(
        Object.entries(popupTypes).map((key, value) => [value, false])
      ),
      dragActive: false
    };

    this.fileInputRef = React.createRef();
  }

  async componentDidMount() {
    addEventListener('popstate', (event) => {
      this.setState(
        {
          currentPrefix:
            event.state && event.state.prefix
              ? event.state.prefix
              : this.props.config.initialPrefix
        },
        () => {
          this.refresh();
        }
      );
    });
    await this.refresh();
  }

  onFileChange = (event) => {
    if (!event.target.files) {
      console.log('nothing selected');
      return;
    }

    const files = [];

    for (let i = 0; i < event.target.files.length; i++) {
      const file = event.target.files[i];
      file.relativePath = file.name;
      files.push(file);
    }

    this.setState({
      selectedFiles: files
    });
    this.showPopup(popupTypes.UPLOAD_FILES);
    this.fileInputRef.current.value = null;
  };

  onBreadcrumbClick = async (e, breadcrumb) => {
    e.preventDefault();
    await this.navigateTo(breadcrumb.prefix);
  };

  onRefreshClick = async () => {
    await this.navigateTo(this.state.currentPrefix);
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
      foldersToDelete
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
      ResponseContentDisposition: 'attachment'
    };

    let url;
    try {
      url = await this.s3.getSignedUrlPromise('getObject', params);
      console.log(url);
      window.location.href = url;
    } catch (ex) {
      this.showErrorPopup(ex);
    }
  };

  async navigateTo(prefix) {
    window.history.pushState(
      { prefix: prefix },
      null,
      this.props.config.rootUrl + prefix
    );
    this.setState({ prefix: prefix });
    await this.refresh(prefix);
  }

  handleFolderClick = async (prefix) => {
    await this.navigateTo(prefix);
  };

  async refresh(prefix) {
    const rootPrefix = this.props.config.rootPrefix;
    const bigdataPrefix = this.props.config.bigdataPrefix;
    const showBigDataMessage = prefix === rootPrefix + bigdataPrefix;
    const params = {
      Bucket: this.state.bucketName,
      Prefix: prefix || this.state.currentPrefix,
      Delimiter: '/'
    };

    const listObjects = async () => {
      let response;
      try {
        response = await this.s3.listObjectsV2(params).promise();
      } catch (ex) {
        console.error('Failed to fetch objects from S3', ex);
        throw new Error(ex);
      }

      const files = response.Contents.filter(
        (file) => file.Key !== params.Prefix
      ).map((file) => ({
        ...file,
        formattedDate: new Date(file.LastModified),
        isSelected: false
      }));

      files.sort(function (a, b) {
        return b.formattedDate - a.formattedDate;
      });

      const teamsFolders =
        params.Prefix === rootPrefix
          ? this.props.config.teamsPrefixes.map((team) => ({
              Prefix: team.prefix,
              isSharedFolder: true,
              isSelected: false
            }))
          : [];

      const bigDataFolder =
        params.Prefix === rootPrefix
          ? [
              {
                Prefix: rootPrefix + bigdataPrefix,
                isBigData: true,
                isSelected: false
              }
            ]
          : [];

      const foldersWithoutBigData = response.CommonPrefixes.filter((folder) => {
        return folder.Prefix !== `${rootPrefix}${bigdataPrefix}`;
      }).map((folder) => ({
        ...folder,
        isBigData: false,
        isSelected: false
      }));
      const folders = teamsFolders
        .concat(bigDataFolder)
        .concat(foldersWithoutBigData);

      return {
        files,
        folders
      };
    };

    try {
      const data = await listObjects();
      this.setState({
        files: data.files,
        folders: data.folders,
        currentPrefix: params.Prefix,
        showBigDataMessage
      });
    } catch (ex) {
      console.log('Error', ex);
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
      })
    });
  };

  onFolderSelect = (folder, isSelected) => {
    this.setState({
      folders: this.state.folders.map((f) => {
        if (f.Prefix === folder.Prefix) {
          f.isSelected = isSelected;
        }
        return f;
      })
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
      file.relativePath = fileEntry.fullPath.substring(1); // Remove leading slash
      return file;
    }

    async function getFiles(dataTransferItemList) {
      const files = [];
      // DataTransferItemList does not support map
      const fileAndDirectoryEntryQueue = [];
      for (let i = 0; i < dataTransferItemList.length; ++i) {
        // At the time of writing no browser supports `getAsEntry`
        fileAndDirectoryEntryQueue.push(
          dataTransferItemList[i].webkitGetAsEntry()
        );
      }

      while (fileAndDirectoryEntryQueue.length > 0) {
        const entry = fileAndDirectoryEntryQueue.shift();
        if (entry.isFile) {
          files.push(await file(entry));
        } else if (entry.isDirectory) {
          fileAndDirectoryEntryQueue.push(
            ...(await entries(entry.createReader()))
          );
        }
      }
      return files;
    }

    this.setState({
      dragActive: false,
      selectedFiles: await getFiles(e.dataTransfer.items)
    });
    this.showPopup(popupTypes.UPLOAD_FILES);
  };

  render() {
    const breadCrumbs = getBreadcrumbs(
      this.props.config.rootPrefix,
      this.props.config.teamsPrefix,
      this.state.currentPrefix
    );

    const currentFolderName = getFolderName(
      this.state.currentPrefix,
      this.props.config.rootPrefix
    );

    return (
      <div className="browser">
        <input
          type="file"
          onChange={this.onFileChange}
          multiple={true}
          ref={this.fileInputRef}
          style={{ display: 'none' }}
        />
        {this.state.error ? (
          <ErrorModal
            error={this.state.error}
            onClose={() => this.setState({ error: null })}
          />
        ) : null}
        {this.state.popups.deleteObjects ? (
          <DeleteObjectsPopup
            open={this.state.popups.deleteObjects}
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
            open={this.state.popups.addFolder}
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
            open={this.state.popups.uploadFiles}
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
          className={`drop-zone ${this.state.dragActive ? 'drag-active' : ''}`}
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
          {this.state.currentPrefix.startsWith('teams/') ? (
            <TeamsPrefixMessage
              team={this.props.config.teamsPrefixes.find((t) =>
                this.state.currentPrefix.startsWith(t.prefix)
              )}
              bucketName={this.state.bucketName}
            />
          ) : null}
        </div>
      </div>
    );
  }
}
