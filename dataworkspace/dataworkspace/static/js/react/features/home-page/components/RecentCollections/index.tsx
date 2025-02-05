import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import { Button } from 'govuk-react';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { LINK_COLOUR, LINK_HOVER_COLOUR, WHITE } from '../../../../constants';
import URLS from '../../../../urls';

export type Collection = {
  name: string;
  url: string;
};

const CollectionTilesContainer = styled('div')`
  margin: ${SPACING_POINTS['5']}px 0 ${SPACING_POINTS['4']}px;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-gap: ${SPACING_POINTS['4']}px;
  word-break: break-word;
  a {
    background-color: ${LINK_COLOUR};
    box-shadow: 0 2px 0 ${LINK_HOVER_COLOUR};
    padding: ${SPACING_POINTS['2']}px;
    color: ${WHITE};
    ${typography.font({ size: 14, weight: 'bold' })};
    text-decoration: none;
    min-height: 111px;
    &:hover {
      background-color: #175a93;
    }
    &:last-child {
      margin-right: 0;
    }
  }
`;

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

const StyledButtonContainer = styled('div')`
  a {
    margin-bottom: ${SPACING_POINTS['4']}px;
  }
`;

const CollectionTile: React.FC<Collection> = ({ url, name }) => (
  <a href={url}>{name}</a>
);

const RecentCollections: React.FC<Record<'collections', Collection[]>> = ({
  collections
}) => (
  <Tile as="article" title="Your recent collections">
    {collections.length ? (
      <>
        <StyledParagraph>
          In collections you can create a space for yourself and colleagues to
          share data, dashboards and notes.
        </StyledParagraph>
        <CollectionTilesContainer>
          {collections.map((collection, index) => (
            <CollectionTile key={index} {...collection} />
          ))}
        </CollectionTilesContainer>
        <Link href={URLS.collections.base}>View all collections</Link>
      </>
    ) : (
      <>
        <StyledParagraph>
          In collections you can create a space for yourself and colleagues to
          share data, dashboards and notes.
        </StyledParagraph>
        <StyledParagraph>
          You've currently not created a collection, or you're not part of an
          existing collection.
        </StyledParagraph>
        <StyledButtonContainer>
          <Button as="a" href={URLS.collections.create}>
            Create a collection
          </Button>
        </StyledButtonContainer>
        <Link href={URLS.external.dataServices.dataWorkspace.collections}>
          Find out more about collections
        </Link>
      </>
    )}
  </Tile>
);

export default RecentCollections;
