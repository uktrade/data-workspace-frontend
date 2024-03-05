import React from 'react';

const  UploadHeaderRow = () => {
    return (
        <tr className="govuk-table__row">
            <th className="govuk-table__header">Name</th>
            <th className="govuk-table__header" style={{ width: '8em' }}>
                Type
            </th>
            <th
                className="govuk-table__header govuk-table__header--numeric"
                style={{ width: '5em' }}
            >
                Size
            </th>
            <th
                className="govuk-table__header govuk-table__header--numeric"
                style={{ width: '7em' }}
            >
                Status
            </th>
        </tr>
    );
};

export default UploadHeaderRow;