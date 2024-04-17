/* eslint-disable */
import React from 'react';

import { bytesToSize } from '../utils';
import { fileQueue } from '../utils';
import { UploadIcon } from '../icons/upload';
import Modal from './Modal';

function UploadHeaderRow() {
  return (
    <tr className="govuk-table__row">
      <th className="govuk-table__header">Name</th>
      <th className="govuk-table__header" style={{ width: '8em' }}>
        Type
      </th>
      <th
        className="govuk-table__header govuk-table__header--numeric"
        style={{ width: '5em' }}
      >
        Size
      </th>
      <th
        className="govuk-table__header govuk-table__header--numeric"
        style={{ width: '7em' }}
      >
        Status
      </th>
    </tr>
  );
}

function UploadFileRow(props) {
  return (
    <tr className="govuk-table__row">
      <td className="govuk-table__cell govuk-table__cell--word-wrapper">{props.file.relativePath}</td>
      <td className="govuk-table__cell govuk-table__cell--word-wrapper">{props.file.type}</td>
      <td className="govuk-table__cell govuk-table__cell--numeric">
        {bytesToSize(props.file.size)}
      </td>
      <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
        {props.file.progress === undefined && props.file.error === undefined ? (
          <span>...</span>
        ) : null}

        {props.file.progress ? (
          <strong
            className={
              'govuk-tag progress-percentage ' +
              (props.file.progress == 100 ? 'progress-percentage-complete' : '')
            }
          >
            {props.file.progress + '%'}
          </strong>
        ) : null}

        {props.file.error !== undefined ? (
          <strong
            className="govuk-tag progress-error"
            title="{ props.file.error }"
          >
            {props.file.error}
          </strong>
        ) : null}
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
      open: props.open
    };
  }

  componentDidMount() {
    document.addEventListener('keydown', this.escFunction, false);
  }

  componentWillUnmount() {
    document.removeEventListener('keydown', this.escFunction, false);
  }

  escFunction = (event) => {
    if (event.key === 'Escape') {
      this.close();
    }
  };

  close = () => {
    if (this.state.isUploading) {
      console.log('Cancel the uploads');
      this.cancelUpload();
    }
    this.props.onCancel();
  };

  onUploadClick = () => {
    const onComplete = this.props.onUploadsComplete;
    const s3 = this.props.s3;
    const bucketName = this.props.bucketName;
    const prefix = this.props.currentPrefix;

    const files = this.state.selectedFiles;
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
            const upload = s3.upload(
              {
                Bucket: bucketName,
                Key: prefix + file.relativePath,
                ContentType: file.type,
                Body: file
              },
              {
                queueSize: connectionsPerFile
              }
            );
            uploads.push(upload);
            await upload
              .on('httpUploadProgress', (event) => {
                file.progress = Math.round(
                  event.total ? (event.loaded * 100.0) / event.total : 0
                );
                this.setState({
                  selectedFiles: files
                });
              })
              .promise();
          }
        } catch (err) {
          isErrored = true;
          file.error = err.code || err.message || err;
          this.setState({
            selectedFiles: files
          });
          throw err;
        } finally {
          remainingUploadCount--;
        }

        if (remainingUploadCount === 0) {
          this.setState({ uploadsComplete: true, isUploading: false });
          if (!isErrored) {
            onComplete();
          }
          f;
        }
      });
    }

    this.cancelUpload = () => {
      isAborted = true;
      uploads.forEach((upload) => {
        upload.abort();
      });
    };

    this.setState({
      isUploading: true
    });
  };

  render() {
    const files = this.state.selectedFiles;
    return (
      <Modal isModalOpen={this.state.open} closeModal={() => onClose()}>
        <div className="popup-container">
          <div
            className="popup-container__overlay"
            onClick={this.props.onCancel}
          ></div>
          <div className="popup-container__modal modal-xl">
            <div className="modal-dialog" style={{ maxWidth: '100%' }}>
              <div className="modal-header">
                <h2 className="modal-title govuk-heading-m" id="upload-title">
                  Upload to {this.state.folderName}
                </h2>
              </div>
              <div className="modal-contents">
                <div className="modal-body">
                  <div className="col-md-18">
                    <div className="panel-body upload-files__table-container">
                      <table
                        className="govuk-table"
                        style={{ tableLayout: 'fixed' }}
                      >
                        <thead>
                          <UploadHeaderRow />
                        </thead>
                        <tbody id="upload-tbody">
                          {files.map((file) => {
                            return (
                              <UploadFileRow
                                file={file}
                                key={file.relativePath}
                              />
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div
                    className="govuk-warning-text"
                    style={{ marginBottom: 0 }}
                  >
                    <span
                      className="govuk-warning-text__icon"
                      aria-hidden="true"
                    >
                      !
                    </span>
                    <strong className="govuk-warning-text__text">
                      <span className="govuk-warning-text__assistive">
                        Warning
                      </span>
                      It is your personal responsibility to protect and handle
                      data appropriately. Data Workspace is not accredited for
                      SECRET or TOP SECRET information. If you are unsure about
                      the information security or data protection of this
                      upload, seek advice on{' '}
                      <a
                        className="govuk-link"
                        href="https://workspace.trade.gov.uk/working-at-dit/policies-and-guidance/guidance/information-classification-and-handling/"
                      >
                        information classification and data handling
                      </a>{' '}
                      or contact your line manager.
                    </strong>
                  </div>
                </div>
                <div
                  className="modal-footer govuk-button-group"
                  style={{ textAlign: 'right' }}
                >
                  {!this.state.uploadsComplete ? (
                    <button
                      autofocus="true"
                      onClick={() => this.onUploadClick(files)}
                      className="govuk-button modal-button"
                      disabled={this.state.isUploading}
                    >
                      <UploadIcon />
                      &nbsp;Upload ({this.state.selectedFiles.length})
                    </button>
                  ) : null}
                  <button
                    id="upload-btn-cancel"
                    type="button"
                    className="govuk-button govuk-button--secondary modal-button"
                    onClick={() => this.close()}
                  >
                    {this.state.isUploading ? 'Cancel' : 'Close'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Modal>
    );
  }
}
