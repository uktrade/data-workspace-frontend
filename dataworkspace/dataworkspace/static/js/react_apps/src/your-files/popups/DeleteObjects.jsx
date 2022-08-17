import React from "react";
import { TrashIcon } from "../icons/trash";

function DeleteTableHeader(props) {
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
    this.state = {
      finished: false,
    };
  }

  render() {
    const objectCount =
      this.props.filesToDelete.length + this.props.foldersToDelete.length;
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
                  <tr className="govuk-table__row">
                    <td className="govuk-table__cell">prefix.Prefix</td>
                    <td className="govuk-table__cell"></td>
                    <td className="govuk-table__cell"></td>
                    <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
                      <span ng-if="!prefix.deleteStarted && !prefix.deleteFinished && !prefix.deleteError">
                        ...
                      </span>
                      <strong
                        ng-if="prefix.deleteStarted && !prefix.deleteFinished && !prefix.deleteError"
                        className="govuk-tag progress-percentage"
                      >
                        Deleting
                      </strong>
                      <strong
                        ng-if="prefix.deleteError"
                        className="govuk-tag progress-error"
                      >
                        prefix.deleteError
                      </strong>
                      <strong
                        ng-if="prefix.deleteFinished"
                        className="govuk-tag progress-percentage-complete"
                      >
                        Deleted
                      </strong>
                    </td>
                  </tr>
                  <tr
                    className="govuk-table__row"
                    ng-repeat="object in model.objects"
                  >
                    <td className="govuk-table__cell">
                      fullpath2filename(object.Key
                    </td>
                    <td className="govuk-table__cell govuk-table__cell--numeric">
                      object.LastModified.toLocaleString
                    </td>
                    <td className="govuk-table__cell govuk-table__cell--numeric">
                      bytesToSize(object.Size)
                    </td>
                    <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
                      <span ng-if="!object.deleteFinished && !object.deleteError">
                        ...
                      </span>
                      <strong
                        ng-if="object.deleteError"
                        className="govuk-tag progress-error"
                      >
                        object.deleteError
                      </strong>
                      <strong
                        ng-if="object.deleteFinished"
                        className="govuk-tag progress-percentage-complete"
                      >
                        Deleted
                      </strong>
                    </td>
                  </tr>
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
                  onClick={this.props.onCancel}
                  className="govuk-button govuk-button--secondary modal-button"
                >
                  {this.state.finished ? "Close" : "Cancel"}
                </button>
                <button
                  id="trash-btn-delete"
                  type="button"
                  className="govuk-button govuk-button--warning modal-button"
                  ng-disabled="model.trashing"
                  ng-if="!model.finished"
                  focus-on="modal::open-end::trash"
                >
                  <TrashIcon />
                  &nbsp;Delete model.count
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
