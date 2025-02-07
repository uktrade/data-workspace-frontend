import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import {
  BLACK,
  DIVIDER_COLOUR,
  FOCUS_COLOUR,
  LINK_COLOUR
} from '../../../../constants';
import URLS from '../../../../urls';

export type RecentToolsProps = {
  name: string;
  url: string | null;
};

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

const RecentToolsList = styled('ul')`
  list-style: none;
  margin: ${SPACING_POINTS['4']}px 0;
  padding: 0;
`;

const RecentToolsListItem = styled('li')`
  display: flex;

  &:first-child div {
    padding-right: ${SPACING_POINTS['4']}px;
  }
  &:last-child div {
    padding-left: ${SPACING_POINTS['4']}px;
    border: none;
  }
  &:only-child div {
    padding: 0;
  }
`;

const RecentToolsLink = styled('a')`
  ${typography.font({ size: 19, weight: 'bold' })};
  color: ${LINK_COLOUR};
  text-decoration: none;
  display: inline-block;
  &:focus {
    color: ${BLACK};
    background-color: ${FOCUS_COLOUR};
    outline: none;
  }
`;

const RecentToolsLinkContainer = styled('div')`
  padding: ${SPACING_POINTS['4']}px 0;
  border-right: 1px solid ${DIVIDER_COLOUR};
`;

const RecentToolsItem: React.FC<RecentToolsProps> = ({ url, name }) => {
  if (url === null) return;
  return (
    <RecentToolsListItem>
      <RecentToolsLinkContainer>
        <RecentToolsLink href={url} target="_blank">
          {name}
        </RecentToolsLink>
      </RecentToolsLinkContainer>
    </RecentToolsListItem>
  );
};

const RecentTools: React.FC<Record<'tools', RecentToolsProps[]>> = ({
  tools
}) => (
  <Tile as="article" title="Your recent tools">
    <StyledParagraph>
      We have a range of tools you can use with datasets.
    </StyledParagraph>
    {tools?.length ? (
      <>
        <RecentToolsList>
          {tools.map(({ url, name }) => (
            <RecentToolsItem name={name} url={url} key={url} />
          ))}
        </RecentToolsList>
        <div>
          <Link href={URLS.tools}>View all tools</Link>
        </div>
      </>
    ) : (
      <>
        <StyledParagraph>You have not used a tool yet.</StyledParagraph>
        <StyledParagraph>
          To start using tools, click on the ‘tools’ navigation item in the
          header or <Link href={URLS.tools}>Visit tools</Link>
        </StyledParagraph>
        <div>
          <Link href={URLS.external.dataServices.dataWorkspace.aboutTools}>
            Find out more about tools
          </Link>
        </div>
      </>
    )}
  </Tile>
);

export default RecentTools;
