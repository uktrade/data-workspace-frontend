import React from 'react';
export function ErrorModal({ error, onClose}) {
  const errors = Object.entries(error || {}).map(([key, value]) => ({ key, value }));
  return (
    <div className="popup-container">
      <div className="popup-container__overlay"></div>
      <div className="popup-container__modal">
        <div className="modal-header">
          <h2 className="modal-title govuk-heading-m" id="trash-title">
            Error {error.code ? `(${error.code})` : null}
          </h2>
        </div>
        <div className="modal-body">
          <div className="panel-body">
            <p className="govuk-body" ng-if="error.errors.length">{error.message}</p>
            <table className="govuk-table" ng-if="error.errors.length">
              <thead>
                <tr className="govuk-table__row">
                  <th className="govuk-table__header">Key</th>
                  <th className="govuk-table__header">Value</th>
                </tr>
              </thead>
              <tbody>
                {errors.map((err, idx) => (
                  <tr className="govuk-table__row" key={idx}>
                    <td className="govuk-table__cell">{err.key}</td>
                    <td className="govuk-table__cell">
                      {err.value.toString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="modal-footer">
          <div className="form-group">
            <div className="govuk-button-group">
              <button
                id="error-btn-close"
                type="button"
                onClick={onClose}
                className="govuk-button govuk-button--secondary modal-button"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
