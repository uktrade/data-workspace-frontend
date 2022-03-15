import React from 'react';

export default function LoadingModal({ message }) {
  return (
    <div id="loading-modal" className="chart-builder-modal">
      <div>
        <div>
          <div className="govuk-!-margin-bottom-5 loading-spinner" />
          <p className="govuk-heading-m">{message}</p>
        </div>
      </div>
    </div>
  )
}
