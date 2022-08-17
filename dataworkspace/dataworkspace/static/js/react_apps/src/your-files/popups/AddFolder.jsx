import React from "react";
import { NewFolderIcon } from "../icons/newfolder";

export class AddFolderPopup extends React.Component {
  constructor(props) {
    super(props);

    this.state = { value: "" };

    this.handleChange = this.handleChange.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
  }

  handleSubmit(event) {
    console.log("on submit");

    const folderName = this.state.value;

    event.preventDefault();
    if (!folderName) {
      return;
    }

    this.props.onSuccess(this.props.currentPrefix, folderName);
  }

  handleChange(event) {
    this.setState({ value: event.target.value });
  }

  render() {
    return (
      <div className="popup-container">
        <div
          className="popup-container__overlay"
          onClick={this.props.onCancel}
        ></div>
        <div
          className="popup-container__modal"
          tabIndex="-1"
          role="dialog"
          aria-labelledby="add-folder-title"
          aria-hidden="true"
        >
          <form
            className="modal-dialog"
            name="add_folder_form"
            onSubmit={() => this.handleSubmit(event)}
          >
            <div className="modal-header">
              <h2 className="modal-title govuk-heading-m">New folder</h2>
            </div>
            <div className="modal-body">
              <div className="govuk-form-group">
                <label className="govuk-label" htmlFor="folder">
                  Folder name
                </label>
                <input
                  className="govuk-input"
                  type="text"
                  value={this.state.value}
                  onChange={this.handleChange}
                  required
                  autoFocus
                />
              </div>
            </div>
            <div className="modal-footer" style={{ textAlign: "right" }}>
              <button
                type="button"
                className="govuk-button govuk-button--secondary modal-button"
                onClick={this.props.onCancel}
              >
                Cancel
              </button>
              <button type="submit" className="govuk-button modal-button">
                <NewFolderIcon />
                &nbsp;Add Folder
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }
}

export class AddFilesPopup extends React.Component {
  constructor(props) {
    super(props);
  }
}
