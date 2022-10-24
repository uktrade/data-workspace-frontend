import React from "react";

import { bytesToSize } from "../utils";
import { fileQueue } from "../utils";
import { UploadIcon } from "../icons/upload";

function UploadHeaderRow() {
  return (
    <tr className="govuk-table__row">
      <th className="govuk-table__header">Name</th>
      <th className="govuk-table__header" style={{ width: "8em" }}>
        Type
      </th>
      <th
        className="govuk-table__header govuk-table__header--numeric"
        style={{ width: "5em" }}
      >
        Size
      </th>
      <th
        className="govuk-table__header govuk-table__header--numeric"
        style={{ width: "7em" }}
      >
        Status
      </th>
    </tr>
  );
}

function UploadFileRow(props) {
  return (
    <tr className="govuk-table__row">
      <td className="govuk-table__cell">{props.file.relativePath}</td>
      <td className="govuk-table__cell">{props.file.type}</td>
      <td className="govuk-table__cell govuk-table__cell--numeric">
        {bytesToSize(props.file.size)}
      </td>
      <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
        {props.file.progress === undefined &&
        props.file.error === undefined ? (
          <span>...</span>
        ) : null}

        {/*<span ng-if="file.progress === undefined && file.error === undefined">...</span>*/}
        {props.file.progress ? (
          <strong className="">{props.file.progress + "%"}</strong>
        ) : null}

        {/*<strong ng-if="file.progress !== undefined && file.error === undefined" className="govuk-tag progress-percentage" ng-class="{'progress-percentage-complete': file.progress == 100}">{{ file.progress + '%' }}</strong>*/}

        {props.file.error !== undefined ? (
          <strong className="govuk-tag progress-error" title="{ props.file.error }">
            {props.file.error}
          </strong>
        ) : null}

        {/*<strong ng-if="file.error !== undefined" className="govuk-tag progress-error" title="{{ file.error }}">{{ file.error }}</strong></td>*/}
      </td>
    </tr>
  );
}

export class UploadFilesPopup extends React.Component {
  constructor(props) {
    /**
     * props is a {}
     * - folderName: The caption for the folder (not the prefix)
     * - onCancel: function to call to dismiss the popup
     * - onUploadsComplete: function to call once upload is complete ... TODO - change the current impl
     * - uploader - Uploader instance
     */

    super(props);
    this.state = {
      remaining: this.props.selectedFiles.length,
      folderName: this.props.folderName,
      selectedFiles: this.props.selectedFiles,
      currentPrefix: this.props.currentPrefix,
      uploadsComplete: false,
      isUploading: false,
    };
  }

  componentDidMount() {
    document.addEventListener("keydown", this.escFunction, false);
  }

  componentWillUnmount() {
    document.removeEventListener("keydown", this.escFunction, false);
  }

  escFunction = (event) => {
    if (event.key === 'Escape') {
      this.close()

    }
  }

  close = () => {
    if (this.state.isUploading) {
      console.log("Cancel the uploads");
      this.cancelUpload();
    }
    this.props.onCancel();
  }

  onUploadClick = () => {
    const onComplete = this.props.onUploadsComplete;
    const s3 = this.props.s3;
    const bucketName = this.props.bucketName;
    const prefix = this.props.currentPrefix;

    const files = this.state.selectedFiles
    var isErrored = false;
    var isAborted = false;
    var remainingUploadCount = files.length;
    var uploads = [];

    const maxConnections = 4;
    const concurrentFiles = Math.min(maxConnections, files.length);
    const connectionsPerFile = Math.floor(maxConnections / concurrentFiles);
    const queue = fileQueue(concurrentFiles);

    for (const file of files) {
      queue(async () => {
        try {
          if (!isAborted) {
            const upload = s3.upload({
                Bucket: bucketName,
                Key: prefix + file.relativePath,
                ContentType: file.type,
                Body: file,
              }, {
                queueSize: connectionsPerFile,
            });
            uploads.push(upload);
            await upload.on("httpUploadProgress", (event) => {
              file.progress = Math.round(event.total ? (event.loaded * 100.0) / event.total : 0)
              this.setState({
                selectedFiles: files
              })
            }).promise();
          }
        } catch (err) {
          isErrored = true;
          file.error = err.code || err.message || err;
          this.setState({
            selectedFiles: files
          })
          throw err
        } finally {
          remainingUploadCount--;
        }

        if (remainingUploadCount === 0) {
          this.setState({ uploadsComplete: true, isUploading: false });
          if (!isErrored) {
            onComplete();
          }f
        }
      });
    }

    this.cancelUpload = () => {
      isAborted = true;
      uploads.forEach((upload) => {
        upload.abort();
      });
    }

    this.setState({
      isUploading: true,
    });
  }

  render() {
    const files = this.state.selectedFiles;
    return (
      <div className="popup-container">
        <div
          className="popup-container__overlay"
          onClick={this.props.onCancel}
        ></div>
        <div className="popup-container__modal modal-xl">
          <div className="modal-header">
            <h2 className="modal-title govuk-heading-m" id="upload-title">
              Upload to {this.state.folderName}
            </h2>
          </div>
          <div className="modal-body">
            <div className="col-md-18">
              <div className="panel-body">
                <table className="govuk-table" style={{ tableLayout: "fixed" }}>
                  <thead>
                    <UploadHeaderRow />
                  </thead>
                  <tbody id="upload-tbody">
                    {files.map((file) => {
                      return <UploadFileRow file={file} key={file.relativePath} />;
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <div className="form-group">
              <div className="govuk-button-group">
                <button
                  id="upload-btn-cancel"
                  type="button"
                  className="govuk-button govuk-button--secondary modal-button"
                  onClick={() => this.close()}
                >
                  {this.state.isUploading ? "Cancel" : "Close"}
                </button>
                {!this.state.uploadsComplete ? <button
                  onClick={() => this.onUploadClick(files)}
                  className="govuk-button modal-button"
                  disabled={this.state.isUploading}
                >
                  <UploadIcon />
                  &nbsp;Upload ({this.state.selectedFiles.length})
                </button> : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
