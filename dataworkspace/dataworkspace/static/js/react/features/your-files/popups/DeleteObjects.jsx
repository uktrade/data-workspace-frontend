/* eslint-disable */
import React from 'react';
import { TrashIcon } from '../icons/trash';
import { bytesToSize, fullPathToFilename, prefixToFolder } from '../utils';
import Modal from './Modal';

const BULK_DELETE_MAX_FILES = 1000;

function DeleteTableHeader() {
  return (
    <thead>
      <tr className="govuk-table__row">
        <th scope="col" className="govuk-table__header">
          Name
        </th>
        <th
          scope="col"
          className="govuk-table__header govuk-table__header--numeric"
          style={{ width: '15em' }}
        >
          Last modified
        </th>
        <th
          scope="col"
          className="govuk-table__header govuk-table__header--numeric"
          style={{ width: '5em' }}
        >
          Size
        </th>
        <th
          scope="col"
          className="govuk-table__header govuk-table__header--numeric"
          style={{ width: '7em' }}
        >
          Status
        </th>
      </tr>
    </thead>
  );
}

export class DeleteObjectsPopup extends React.Component {
  constructor(props) {
    super(props);
    this.abort = () => {};
    this.state = {
      open: props.open,
      finished: false,
      trashing: false,
      aborted: false,
      foldersToDelete: this.props.foldersToDelete.map((folder) => ({
        ...folder,
        deleteStarted: false,
        deleteFinished: false,
        deleteError: null
      })),
      filesToDelete: this.props.filesToDelete.map((file) => ({
        ...file,
        deleteStarted: false,
        deleteFinished: false,
        deleteError: null
      }))
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
      this.onCloseClick();
    }
  };

  onDeleteClick = async () => {
    const s3 = this.props.s3;
    const bucketName = this.props.bucketName;
    const foldersToDelete = this.state.foldersToDelete;
    const filesToDelete = this.state.filesToDelete;

    const numObjects = foldersToDelete.length + filesToDelete.length;
    const maxConnections = 4;

    var isErrored = false;
    var isAborted = false;
    var remainingDeleteCount = numObjects;
    var keysToDelete = [];

    this.abort = () => {
      isAborted = true;
    };

    const updateDeleteState = (fileOrFolder, newState) => {
      this.setState({
        foldersToDelete: this.state.foldersToDelete.map((f) => {
          return f.Prefix === fileOrFolder.Prefix ? { ...f, ...newState } : f;
        }),
        filesToDelete: this.state.filesToDelete.map((f) => {
          return f.Key === fileOrFolder.Key ? { ...f, ...newState } : f;
        })
      });
    };

    const deleteKeys = async () => {
      const rootFileOrFolders = keysToDelete.map(
        ([rootFileOrFolder, key]) => rootFileOrFolder
      );
      try {
        await s3
          .deleteObjects({
            Bucket: bucketName,
            Delete: {
              Objects: keysToDelete.map(([rootFileOrFolder, key]) => ({
                Key: key
              }))
            }
          })
          .promise();
      } catch (err) {
        isErrored = true;
        for (const rootFileOrFolder of rootFileOrFolders) {
          updateDeleteState(rootFileOrFolder, {
            deleteError: err.code || err.message || err
          });
        }
        throw err;
      } finally {
        keysToDelete = [];
      }
      for (const rootFileOrFolder of rootFileOrFolders) {
        updateDeleteState(rootFileOrFolder, { deleteFinished: true });
      }
    };

    const flushDelete = async () => {
      if (keysToDelete.length) await deleteKeys();
    };

    const scheduleDelete = async (rootFolder, key) => {
      keysToDelete.push([rootFolder, key]);
      if (keysToDelete.length >= BULK_DELETE_MAX_FILES) {
        await deleteKeys();
      }
    };

    for (const folder of foldersToDelete) {
      updateDeleteState(folder, { deleteStarted: true });
      let continuationToken = null;
      let isTruncated = true;
      while (isTruncated && !isAborted) {
        // Find objects at or under the prefix...
        let response;
        try {
          response = await s3
            .listObjectsV2({
              Bucket: bucketName,
              Prefix: folder.Prefix,
              ContinuationToken: continuationToken
            })
            .promise();
          continuationToken = response.NextContinuationToken;
          isTruncated = response.IsTruncated;
        } catch (err) {
          isErrored = true;
          updateDeleteState(folder, {
            deleteError: err.code || err.message || err
          });
          throw err;
        }
        // ... and delete them
        for (let j = 0; j < response.Contents.length && !isAborted; ++j) {
          await scheduleDelete(folder, response.Contents[j].Key);
        }
      }
    }
    for (const file of filesToDelete) {
      if (isAborted) break;
      updateDeleteState(file, { deleteStarted: true });
      await scheduleDelete(file, file.Key);
    }

    if (isAborted) return;
    await flushDelete();

    this.setState({ finished: true });
    if (!isErrored) {
      this.props.onSuccess();
    }
  };

  onCloseClick = () => {
    this.abort();
    this.props.onClose();
  };

  render() {
    const folders = this.state.foldersToDelete;
    const files = this.state.filesToDelete;
    const objectCount = files.length + folders.length;
    return (
      <Modal isModalOpen={this.state.open} closeModal={() => onClose()}>
        <div className="popup-container">
          <div className="popup-container__overlay"></div>
          <div className="popup-container__modal">
            <div className="modal-dialog" style={{ maxWidth: '100%' }}>
              <div className="modal-header">
                <h2 className="modal-title govuk-heading-m" id="trash-title">
                  {`Confirm delete of ${objectCount} object${
                    objectCount > 1 ? 's' : ''
                  }`}
                </h2>
              </div>
              <div className="modal-contents">
                <div className="modal-body">
                  <div className="panel-body">
                    <table
                      className="govuk-table"
                      style={{ tableLayout: 'fixed' }}
                    >
                      <DeleteTableHeader />
                      <tbody id="s3objects-tbody">
                        {folders.map((folder) => {
                          const folderName = prefixToFolder(folder.Prefix);
                          return (
                            <tr
                              key={folder.Prefix}
                              className="govuk-table__row"
                            >
                              <td className="govuk-table__cell">
                                {folderName}
                              </td>
                              <td className="govuk-table__cell"></td>
                              <td className="govuk-table__cell"></td>
                              <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
                                {folder.deleteStarted ||
                                folder.deleteFinished ||
                                folder.deleteError ? null : (
                                  <span>...</span>
                                )}

                                {folder.deleteStarted &&
                                !folder.deleteFinished &&
                                !folder.deleteError ? (
                                  <strong
                                    className={'govuk-tag progress-percentage'}
                                  >
                                    Deleting
                                  </strong>
                                ) : null}

                                {folder.deleteError ? (
                                  <strong
                                    className={'govuk-tag progress-error'}
                                  >
                                    {folder.deleteError}
                                  </strong>
                                ) : null}

                                {folder.deleteFinished ? (
                                  <strong
                                    className={
                                      'govuk-tag progress-percentage-complete'
                                    }
                                  >
                                    Deleted
                                  </strong>
                                ) : null}
                              </td>
                            </tr>
                          );
                        })}
                        {files.map((file) => {
                          const filename = fullPathToFilename(file.Key);
                          return (
                            <tr
                              key={file.Key}
                              className="govuk-table__row"
                              ng-repeat="object in model.objects"
                            >
                              <td className="govuk-table__cell">{filename}</td>
                              <td className="govuk-table__cell govuk-table__cell--numeric">
                                {file.LastModified.toLocaleString()}
                              </td>
                              <td className="govuk-table__cell govuk-table__cell--numeric">
                                {bytesToSize(file.Size)}
                              </td>
                              <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
                                {!file.deleteFinished && !file.deleteError ? (
                                  <span>...</span>
                                ) : null}

                                {file.deleteError ? (
                                  <strong
                                    className={'govuk-tag progress-error'}
                                  >
                                    {file.deleteError}
                                  </strong>
                                ) : null}

                                {file.deleteFinished ? (
                                  <strong
                                    className={
                                      'govuk-tag progress-percentage-complete'
                                    }
                                  >
                                    Deleted
                                  </strong>
                                ) : null}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="modal-footer govuk-button-group">
                  {!this.state.finished ? (
                    <button
                      autofocus="true"
                      id="trash-btn-delete"
                      type="button"
                      onClick={() => this.onDeleteClick()}
                      className="govuk-button govuk-button--warning modal-button"
                      disabled={this.state.trashing || this.state.finished}
                    >
                      <TrashIcon />
                      &nbsp;Delete {objectCount}
                    </button>
                  ) : null}
                  <button
                    id="trash-btn-cancel"
                    type="button"
                    onClick={() => this.onCloseClick()}
                    className="govuk-button govuk-button--secondary modal-button"
                  >
                    Close
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
