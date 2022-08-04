import React from "react";
import "./Popups.css";
import { bytesToSize } from "../utils";

export class UploadFilesPopup extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      remaining: 0,
    };
    this.close = this.close.bind(this);
  }

  close() {
    console.log(this.state.remaining);
    this.props.onCancel();
  }

  render() {
    const files = Array.from(this.props.selectedFiles);
    return (
      <>
        <div className="popup-overlay" onClick={this.props.onCancel}></div>
        <div className="popup-modal">
          <div className="modal-header">
            <h2 className="modal-title govuk-heading-m" id="upload-title">
              Upload to {this.props.folderName}
            </h2>
          </div>
          <div className="modal-body">
            <div className="col-md-18">
              <div className="panel-body">
                <table className="govuk-table" style={{ tableLayout: "fixed" }}>
                  <thead>
                    <tr className="govuk-table__row">
                      <th className="govuk-table__header">Name</th>
                      <th
                        className="govuk-table__header"
                        style={{ width: "8em" }}
                      >
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
                  </thead>
                  <tbody id="upload-tbody">
                    {files.map((file) => {
                      return (
                        <tr
                          className="govuk-table__row"
                          ng-repeat="file in model.files"
                        >
                          <td className="govuk-table__cell">
                            {file.name}
                          </td>
                          <td className="govuk-table__cell">{file.type}</td>
                          <td className="govuk-table__cell govuk-table__cell--numeric">
                            {bytesToSize(file.size)}
                          </td>
                          <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
                            {/*<span ng-if="file.progress === undefined && file.error === undefined">...</span>*/}
                            {/*<strong ng-if="file.progress !== undefined && file.error === undefined" className="govuk-tag progress-percentage" ng-class="{'progress-percentage-complete': file.progress == 100}">{{ file.progress + '%' }}</strong>*/}
                            {/*<strong ng-if="file.error !== undefined" className="govuk-tag progress-error" title="{{ file.error }}">{{ file.error }}</strong></td>*/}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div className="modal-footer">
            <div className="form-group">
              <div className="col-sm-offset-2 col-sm-10">
                <button
                  id="upload-btn-cancel"
                  type="button"
                  className="govuk-button govuk-button--secondary modal-button"
                  onClick={() => this.close()}
                >
                  {this.state.remaining === 0 ? "Close" : "Cancel"}
                </button>
                <button
                  id="upload-btn-upload"
                  type="submit"
                  className="govuk-button modal-button"
                >
                  <svg
                    aria-hidden="true"
                    focusable="false"
                    data-prefix="fas"
                    data-icon="cloud-upload-alt"
                    className="button-icon svg-inline--fa fa-cloud-upload-alt fa-w-20"
                    role="img"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 640 512"
                  >
                    <path
                      fill="currentColor"
                      d="M537.6 226.6c4.1-10.7 6.4-22.4 6.4-34.6 0-53-43-96-96-96-19.7 0-38.1 6-53.3 16.2C367 64.2 315.3 32 256 32c-88.4 0-160 71.6-160 160 0 2.7.1 5.4.2 8.1C40.2 219.8 0 273.2 0 336c0 79.5 64.5 144 144 144h368c70.7 0 128-57.3 128-128 0-61.9-44-113.6-102.4-125.4zM393.4 288H328v112c0 8.8-7.2 16-16 16h-48c-8.8 0-16-7.2-16-16V288h-65.4c-14.3 0-21.4-17.2-11.3-27.3l105.4-105.4c6.2-6.2 16.4-6.2 22.6 0l105.4 105.4c10.1 10.1 2.9 27.3-11.3 27.3z"
                    ></path>
                  </svg>
                  &nbsp;Upload ({files.length})
                </button>
              </div>
            </div>
          </div>
        </div>
      </>
    );
  }
}
