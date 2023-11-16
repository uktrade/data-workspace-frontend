import React from 'react';

import {
    MEDIA_QUERIES,
    SPACING_POINTS  
} from '@govuk-react/constants';
import { H2 } from 'govuk-react';
import styled from 'styled-components';

import GetHelp from '../../components/GetHelp';
import OtherSupport from '../../components/OtherSupport';
import {
    WHITE
} from '../../constants';

const SupportYouContainer = styled('div')`
    padding: ${SPACING_POINTS[4]}px;
    background-color: ${WHITE};
`;

const TilesContainer = styled('div')`
    ${MEDIA_QUERIES.DESKTOP} {
        display: grid;
        grid-template-rows: 1;
        grid-template-columns: repeat(2, 1fr);
        column-gap: ${SPACING_POINTS[6]}px;
    }

    &:first-child {
        grid-column-start: 1;
        grid-column-end: 1;
    }
    &:nth-child(2) {
        grid-column-start: 2;
        grid-column-end: 2;
    }
`;

const SupportYou: React.FC = () => {
    return (
        <SupportYouContainer>
            <H2>
                How can we support you?
            </H2>
            <TilesContainer>
                <GetHelp />
                <OtherSupport />
            </TilesContainer>
        </SupportYouContainer>
    );
};

export default SupportYou;
