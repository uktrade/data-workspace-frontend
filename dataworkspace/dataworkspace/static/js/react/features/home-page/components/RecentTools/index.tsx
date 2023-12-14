import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { DIVIDER_COLOUR } from '../../../../constants';
import URLS from '../../../../urls';

export type RecentToolsProps = {
  title: string;
  url: string | null;
};

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

const RecentToolsList = styled('ul')`
  list-style: none;
  margin: ${SPACING_POINTS['4']}px 0;
  padding: 0;
  display: flex;
`;

const RecentToolsListItem = styled('li')`
  &:first-child a {
    padding-right: ${SPACING_POINTS['4']}px;
  }
  &:last-child a {
    padding-left: ${SPACING_POINTS['4']}px;
    border: none;
  }
  &:only-child a {
    padding: 0;
  }
`;

const RecentToolsLink = styled(Link)`
  ${typography.font({ size: 19, weight: 'bold' })};
  text-decoration: none;
  padding: ${SPACING_POINTS['4']}px 0;
  border-right: 1px solid ${DIVIDER_COLOUR};
  display: inline-block;
`;

const RecentToolsItem: React.FC<RecentToolsProps> = ({ url, title }) => {
  if (url === null) return;
  return (
    <RecentToolsListItem>
      <RecentToolsLink href={url} target="_blank">
        {title}
      </RecentToolsLink>
    </RecentToolsListItem>
  );
};

const RecentTools: React.FC<Record<'tools', RecentToolsProps[]>> = ({
  tools
}) => (
  <Tile title="Your recent tools">
    <StyledParagraph>
      We have a range of tools you can use with datasets.
    </StyledParagraph>
    {tools?.length ? (
      <>
        <RecentToolsList>
          {tools.map(({ url, title }) => (
            <RecentToolsItem title={title} url={url} key={url} />
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
