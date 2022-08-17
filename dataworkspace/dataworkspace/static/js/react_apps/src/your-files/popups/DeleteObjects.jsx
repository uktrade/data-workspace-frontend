import React from "react";

export class DeleteObjectsPopup extends React.Component {
  constructor(props) {
    super(props);
  }

  render() {
    return (
      <div className="popup-container">
        <div className="popup-container__overlay"></div>
        <div
          className="popup-container__modal"
          tabIndex="-1"
          role="dialog"
          aria-labelledby="delete-objects-title"
          aria-hidden="true"
        >
          <form className="modal-dialog" name="delete_objects_form">
            <div className="modal-header">
              <h2 className="modal-title govuk-heading-m">Delete</h2>
            </div>
          </form>
        </div>
      </div>
    );
  }
}
