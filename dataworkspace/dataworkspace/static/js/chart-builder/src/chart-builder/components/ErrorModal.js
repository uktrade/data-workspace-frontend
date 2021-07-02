import React from 'react';

export default function ErrorModal({ title, message, backLink }) {
  return (
    <div id="error-modal" className="chart-builder-modal">
      <div>
        <div className="govuk-error-summary">
          <div className="govuk-warning-text">
            <span className="govuk-warning-text__icon" aria-hidden="true">!</span>
            <strong className="govuk-warning-text__text">
              <span className="govuk-warning-text__assistive">Warning</span>
              {title}
            </strong>
          </div>
          <p className="govuk-body">{message}</p>
          <div className="button-wrap">
            <a className="govuk-button govuk-button--secondary" href={backLink}>
            Back
          </a>
          </div>
        </div>
      </div>
    </div>
  )
}
