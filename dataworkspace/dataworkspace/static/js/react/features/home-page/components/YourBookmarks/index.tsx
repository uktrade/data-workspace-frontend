import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { DIVIDER_COLOUR, LINK_COLOUR } from '../../../../constants';

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

export type YourBookmarkProps = {
    name: string;
    url: string;
};

const YourBookmarkListItem: React.FC<YourBookmarkProps> = ({ name, url }) => (
    <li>
        {/* Styled component here */}
    </li>
);

const YourBookmarks: React.FC<Record<'bookmarks', YourBookmarkProps[]>> = ({
    bookmarks
}) => (
    <Tile title="Your bookmarks">
        {bookmarks?.length ? (
            // map bookmarks here
        ) : (
            // alt text here
        )}
    </Tile>
);