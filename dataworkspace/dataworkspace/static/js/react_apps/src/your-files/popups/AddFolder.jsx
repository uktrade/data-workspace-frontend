import React from "react";
import "./Popups.scss";

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
                <svg
                  aria-hidden="true"
                  focusable="false"
                  data-prefix="fas"
                  data-icon="folder-plus"
                  className="button-icon svg-inline--fa fa-folder-plus fa-w-16"
                  role="img"
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 512 512"
                  width="18"
                  height="18"
                >
                  <path
                    fill="currentColor"
                    d="M464 128H272l-64-64H48C21.49 64 0 85.49 0 112v288c0 26.51 21.49 48 48 48h416c26.51 0 48-21.49 48-48V176c0-26.51-21.49-48-48-48zm-96 168c0 8.84-7.16 16-16 16h-72v72c0 8.84-7.16 16-16 16h-16c-8.84 0-16-7.16-16-16v-72h-72c-8.84 0-16-7.16-16-16v-16c0-8.84 7.16-16 16-16h72v-72c0-8.84 7.16-16 16-16h16c8.84 0 16 7.16 16 16v72h72c8.84 0 16 7.16 16 16v16z"
                  ></path>
                </svg>
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
