import React from 'react';

import { bytesToSize } from '../../utils';

const UploadFileRow = (props) => {
    return (
        <tr className="govuk-table__row">
            <td className="govuk-table__cell">{props.file.relativePath}</td>
            <td className="govuk-table__cell">{props.file.type}</td>
            <td className="govuk-table__cell govuk-table__cell--numeric">
                {bytesToSize(props.file.size)}
            </td>
            <td className="govuk-table__cell govuk-table__cell--numeric govuk-table__cell-progress">
                {props.file.progress === undefined && props.file.error === undefined ? (
                    <span>...</span>
                ) : null}

                {props.file.progress ? (
                    <strong
                        className={
                        'govuk-tag progress-percentage ' +
                        (props.file.progress == 100 ? 'progress-percentage-complete' : '')
                        }
                    >
                        {props.file.progress + '%'}
                    </strong>
                ) : null}

                {props.file.error !== undefined ? (
                    <strong
                        className="govuk-tag progress-error"
                        title="{ props.file.error }"
                    >
                        {props.file.error}
                    </strong>
                ) : null}
            </td>
        </tr>
    );
};

export default UploadFileRow;