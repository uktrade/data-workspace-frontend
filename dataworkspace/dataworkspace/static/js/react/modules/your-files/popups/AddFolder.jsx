import React from "react";
import { NewFolderIcon } from "../icons/newfolder";

export class AddFolderPopup extends React.Component {
  constructor(props) {
    super(props);

    this.state = { value: "" };
    this.handleChange = this.handleChange.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
  }

  componentDidMount() {
    document.addEventListener("keydown", this.escFunction, false);
  }

  componentWillUnmount() {
    document.removeEventListener("keydown", this.escFunction, false);
  }

  escFunction = (event) => {
    if (event.key === 'Escape') {
      this.props.onClose();
    }
  }

  async handleSubmit(event) {
    console.log("on submit");
    event.preventDefault();

    const folderName = this.state.value;
    if (!folderName) return;

    const s3 = this.props.s3;
    const bucketName = this.props.bucketName;
    const currentPrefix = this.props.currentPrefix;
    const onSuccess = this.props.onSuccess;
    const onClose = this.props.onClose;
    const onError = this.props.onError;

    const removeSlashes = (text) => {
      return text.replace(/^\/+/g, "").replace(/\/+$/g, "");
    }

    console.log("createFolder", currentPrefix, folderName);
    const folder = currentPrefix + removeSlashes(folderName) + "/";
    console.log(folder);
    const params = { Bucket: bucketName, Key: folder };

    let canCreate = false;
    // Slightly awkward since a 404 is converted to an exception
    try {
      await s3.headObject(params).promise();
    } catch (err) {
      canCreate = err.code === "NotFound";
      if (!canCreate) {
        onError(err);
        return;
      }
    }
    if (!canCreate) {
      alert("Error: folder or object already exists at " + params.Key);
      return;
    }

    try {
      await s3.putObject(params).promise();
    } catch(err) {
      onError(err);
      return
    }

    onSuccess();
    onClose();
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
            <div className="modal-footer" style={{textAlign : "right"}}>
              <button
                type="button"
                className="govuk-button govuk-button--secondary modal-button"
                onClick={this.props.onClose}
              >
                Cancel
              </button>
              &nbsp;
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
