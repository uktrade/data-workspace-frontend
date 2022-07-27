import React from 'react';

export default function QueryErrorModal({ title, message, backLink }) {
  return (
    <div id="error-modal" className="chart-builder-modal">
      <div>
        <div className="govuk-error-summary">
          <div className="govuk-warning-text">
            <span className="govuk-warning-text__icon" aria-hidden="true">!</span>
            <strong className="govuk-warning-text__text">
              <span className="govuk-warning-text__assistive">Warning</span>
              Failed to run your query
            </strong>
          </div>
          <p className="govuk-body">An error occurred while running your query.</p>
          <div className="govuk-body-s">
            <p className="govuk-body-s">Common causes of query errors can be:</p>
            <ul className="govuk-list govuk-list--bullet govuk-list--spaced govuk-body-s">
              <li>
                Too many columns in the output.
                <br/>
                <small>Try removing all but the columns you need for your chart.</small>
              </li>
              <li>
                Long running query.
                <br/>
                <small>Try simplifying the query to reduce runtime.</small>
              </li>
            </ul>
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
