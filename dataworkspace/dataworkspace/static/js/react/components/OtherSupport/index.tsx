import React from 'react';

import {
    SPACING,
    // SPACING_POINTS
} from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import { H3 } from 'govuk-react';
import styled from 'styled-components';

import Tile from '../Tile';

const StyledParagraph = styled('p')`
    margin: 0 0 ${SPACING.SCALE_5} 0;
    ${typography.font({ size: 16 })};

    &:last-child {
        margin-bottom: 0;
    }
`;

const hrefToSupport = `
    https://data.trade.gov.uk/support-and-feedback/
`;
const hrefToCommunityChannel = `
    https://teams.microsoft.com/l/team/19%3Ac1f08445f252403982e22a3
    87b30b4ca%40thread.skype/conversations?groupId=748264d0-f2a0-4e
    13-afa0-22c152ea7cb9&tenantId=8fa217ec-33aa-46fb-ad96-dfe68006b
    b86
`;
const hrefToTeamsChannel = `
    https://data-services-help.trade.gov.uk/data-workspace/updates/
`;

const OtherSupport: React.FC = () => {
    return (
        <Tile title='Other ways of support'>
            <H3 size={'SMALL'}>Message</H3>
            <StyledParagraph>
                <Link href={hrefToSupport}>Contact us</Link> if you have a 
                question, problem or suggestion.
            </StyledParagraph>
            <H3 size={'SMALL'}>Community</H3>
            <StyledParagraph>
                Join the <Link href={hrefToCommunityChannel}>Data Workspace community channel</Link> on
                Microsoft Teams to connect with colleagues.
            </StyledParagraph>
            <H3 size={'SMALL'}>Work</H3>
            <StyledParagraph>
                Find out what we are working on by visiting <Link href={hrefToTeamsChannel}>What's new page</Link>
            </StyledParagraph>
        </Tile>
    );
};

export default OtherSupport;
