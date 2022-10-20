import React from "react";

import { bytesToSize } from "../utils";
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
        style={{ width: "6em" }}
      >
        Status
      </th>
    </tr>
  );
}

function UploadFileRow(props) {
  return (
    <tr className="govuk-table__row">
      <td className="govuk-table__cell">{props.file.name}</td>
      <td className="govuk-table__cell">{props.file.type}</td>
      <td className="govuk-table__cell govuk-table__cell--numeric">
        {bytesToSize(props.file.size)}
      </td>
      <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
        {props.file.progress === undefined &&
        props.file.errors === undefined ? (
          <span>...</span>
        ) : null}

        {/*<span ng-if="file.progress === undefined && file.error === undefined">...</span>*/}
        {props.file.progress ? (
          <strong className="">{props.file.progress + "%"}</strong>
        ) : null}

        {/*<strong ng-if="file.progress !== undefined && file.error === undefined" className="govuk-tag progress-percentage" ng-class="{'progress-percentage-complete': file.progress == 100}">{{ file.progress + '%' }}</strong>*/}

        {props.file.error !== undefined ? (
          <strong className="govuk-tag progress-error" title="{ file.error }">
            {file.error}
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
    this.close = this.close.bind(this);
    this.onUploadClick = this.onUploadClick.bind(this);
  }

  close() {
    if (this.state.isUploading) {
      console.log("Cancel the uploads");
      this.cancelUpload();
    }
    this.props.onCancel();
  }

  onUploadClick() {
    const uploader = this.props.uploader;
    const onComplete = this.props.onUploadsComplete;

    uploader.on("complete", () => {
      this.setState({ uploadsComplete: true, isUploading: false });
      onComplete();
    });

    uploader.on("cancelled", () => {
      this.setState({ isUploading: false });
    });

    uploader.on("upload:start", (file) => {
      console.log("Start", file);
    });

    uploader.on("upload:failed", (file) => {
      console.log("failed", file);
    });

    uploader.on("upload:complete", (file) => {
      this.setState((state) => {
        return {
          remaining: state.remaining - 1,
        };
      });
    });

    uploader.on("upload:progress", (uploadingFile, percent) => {
      console.log(percent, uploadingFile);

      this.setState((state) => {
        const selectedFiles = state.selectedFiles.map((file) => {
          if (uploadingFile === file) {
            const progress = Math.round(percent);
            console.log("update progress to", progress);
            file.progress = progress;
          }

          return file;
        });

        return {
          selectedFiles,
        };
      });
    });

    this.setState({
      remaining: this.state.selectedFiles.length,
      isUploading: true,
    });
    this.cancelUpload = uploader.start(this.state.selectedFiles, this.state.currentPrefix);
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
                      return <UploadFileRow file={file} key={file.name} />;
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
                <button
                  onClick={() => this.onUploadClick(files)}
                  className="govuk-button modal-button"
                  disabled={
                    this.state.uploadsComplete || this.state.isUploading
                  }
                >
                  <UploadIcon />
                  &nbsp;Upload ({this.state.remaining})
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
