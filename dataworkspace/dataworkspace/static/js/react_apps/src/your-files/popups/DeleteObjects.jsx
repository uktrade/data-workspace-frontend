import React from "react";
import { TrashIcon } from "../icons/trash";
import { bytesToSize, fullPathToFilename, prefixToFolder } from "../utils";

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
          style={{ width: "15em" }}
        >
          Last modified
        </th>
        <th
          scope="col"
          className="govuk-table__header govuk-table__header--numeric"
          style={{ width: "5em" }}
        >
          Size
        </th>
        <th
          scope="col"
          className="govuk-table__header govuk-table__header--numeric"
          style={{ width: "6em" }}
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
      finished: false,
      trashing: false,
      aborted: false,
      foldersToDelete: this.props.foldersToDelete.map((folder) => ({
        ...folder,
        deleteStarted: false,
        deleteFinished: false,
        deleteError: null,
      })),
      filesToDelete: this.props.filesToDelete.map((file) => ({
        ...file,
        deleteStarted: false,
        deleteFinished: false,
        deleteError: null,
      })),
    };
  }

  updateDeleteState(fileOrFolder, newState) {
    this.setState({
      foldersToDelete: this.state.foldersToDelete.map((f) => {
        return f.Prefix === fileOrFolder.Prefix ? { ...f, ...newState } : f;
      }),
      filesToDelete: this.state.filesToDelete.map((f) => {
        return f.Key === fileOrFolder.Key ? { ...f, ...newState } : f;
      }),
    });
  }

  onDeleteClick = () => {
    const deleter = this.props.deleter;

    this.setState({
      trashing: true,
    });

    deleter.on("delete:start", (fileOrFolder) => {
      this.updateDeleteState(fileOrFolder, { deleteStarted: true });
    });

    deleter.on("delete:error", (fileOrFolder, error) => {
      this.updateDeleteState(fileOrFolder, { deleteError: error });
    });

    deleter.on("delete:finished", (fileOrFolder) => {
      this.updateDeleteState(fileOrFolder, { deleteFinished: true });
    });

    deleter.on("delete:done", () => {
      this.setState({ finished: true });
    });

    this.abort = deleter.start(this.state.foldersToDelete, this.state.filesToDelete);
  };

  onCloseClick = () => {
    this.setState({
      aborted: true,
    });
    this.props.onCancel();
  };

  render() {
    const folders = this.state.foldersToDelete;
    const files = this.state.filesToDelete;
    const objectCount = files.length + folders.length;
    return (
      <div className="popup-container">
        <div className="popup-container__overlay"></div>
        <div className="popup-container__modal modal-xl">
          <div className="modal-header">
            <h2 className="modal-title govuk-heading-m" id="trash-title">
              {`Confirm delete of ${objectCount} object${
                objectCount > 1 ? "s" : ""
              }`}
            </h2>
          </div>
          <div className="modal-body">
            <div className="panel-body">
              <table className="govuk-table" style={{ tableLayout: "fixed" }}>
                <DeleteTableHeader />
                <tbody id="s3objects-tbody">
                  {folders.map((folder) => {
                    const folderName = prefixToFolder(folder.Prefix);
                    return (
                      <tr key={folder.Prefix} className="govuk-table__row">
                        <td className="govuk-table__cell">{folderName}</td>
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
                            <strong className={"govuk-tag progress-percentage"}>
                              Deleting
                            </strong>
                          ) : null}

                          {folder.deleteError ? (
                            <strong className={"govuk-tag progress-error"}>
                              folder.deleteError
                            </strong>
                          ) : null}

                          {folder.deleteFinished ? (
                            <strong
                              className={
                                "govuk-tag progress-percentage-complete"
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
                            <strong className={"govuk-tag progress-error"}>
                              {file.deleteError}
                            </strong>
                          ) : null}

                          {file.deleteFinished ? (
                            <strong
                              className={
                                "govuk-tag progress-percentage-complete"
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
          <div className="modal-footer">
            <div className="form-group">
              <div className="govuk-button-group">
                <button
                  id="trash-btn-cancel"
                  type="button"
                  onClick={() => this.onCloseClick()}
                  className="govuk-button govuk-button--secondary modal-button"
                >
                  {this.state.finished ? "Close" : "Cancel"}
                </button>
                {!this.state.finished ? <button
                  id="trash-btn-delete"
                  type="button"
                  onClick={() => this.onDeleteClick()}
                  className="govuk-button govuk-button--warning modal-button"
                  disabled={this.state.trashing || this.state.finished}
                >
                  <TrashIcon />
                  &nbsp;Delete {objectCount}
                </button> : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
