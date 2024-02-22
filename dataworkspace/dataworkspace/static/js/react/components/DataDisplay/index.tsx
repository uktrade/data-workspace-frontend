import React from 'react';

import {
  FONT_SIZE,
  FONT_WEIGHTS,
  MEDIA_QUERIES,
  SPACING,
  SPACING_POINTS
} from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import { H2, Link, UnorderedList } from 'govuk-react';
import styled, { css } from 'styled-components';

import { TransformedDataUsageResponse } from '../../types/index';

const PrimaryLayout = css`
  &:first-child {
    grid-column-start: 3;
    grid-column-end: 5;
  }
  &:nth-child(2) {
    grid-column-start: 5;
    grid-column-end: 7;
    border: none;
  }
  &:nth-child(3) {
    grid-column-start: 2;
    grid-column-end: 4;
    grid-row-start: 2;
  }
  &:nth-child(4) {
    grid-column-start: 4;
    grid-column-end: 6;
    grid-row-start: 2;
  }
  &:nth-child(5) {
    grid-column-start: 6;
    grid-column-end: 8;
    grid-row-start: 2;
    border: none;
  }
`;
const SecondaryLayout = css`
  &:first-child {
    grid-column-start: 3;
    grid-column-end: 5;
  }
  &:nth-child(2) {
    grid-column-start: 5;
    grid-column-end: 7;
    border: none;
  }
  &:nth-child(3) {
    grid-column-start: 3;
    grid-column-end: 5;
    grid-row-start: 2;
  }
  &:nth-child(4) {
    grid-column-start: 5;
    grid-column-end: 7;
    grid-row-start: 2;
    border: none;
  }
`;

const DataDisplayList = styled(UnorderedList)`
  padding: 0;
  margin: ${SPACING_POINTS[9]}px 0 ${SPACING_POINTS[9]}px;
  list-style: none;

  ${MEDIA_QUERIES.DESKTOP} {
    display: grid;
    grid-template-rows: 2;
    grid-template-columns: repeat(8, 1fr);
    row-gap: ${SPACING_POINTS[9]}px;
  }
`;

const DataDisplayListItem = styled.li<{ secondary: boolean }>`
  text-align: center;
  font-size: 38px;
  font-weight: ${FONT_WEIGHTS.bold};
  margin: ${SPACING_POINTS[6]}px 0;
  padding: ${SPACING_POINTS[2]}px;

  span {
    display: block;
    font-size: ${FONT_SIZE.SIZE_14};
    font-weight: ${FONT_WEIGHTS.regular};
  }

  ${MEDIA_QUERIES.DESKTOP} {
    font-size: 48px;
    border-right: 1px solid #b1b4b6;
    margin: 0;

    span {
      font-size: ${FONT_SIZE.SIZE_19};
    }
    ${(props) => (props.secondary ? SecondaryLayout : PrimaryLayout)};
  }
`;

const DataDisplayContainer = styled('div')`
  margin-top: ${SPACING_POINTS['8']}px;
`;

const StyledParagraph = styled('p')`
  margin: ${SPACING.SCALE_3} 0;
  ${typography.font({ size: 19 })};
`;

type DataDisplayProps = {
  data: TransformedDataUsageResponse;
  title?: string;
  historyUrl?: string;
  subTitle?: string | null;
  secondary?: boolean;
  footerNote?: React.ReactNode;
};

const DataDisplay: React.FC<DataDisplayProps> = ({
  data = [],
  title = 'Data usage',
  subTitle = null,
  historyUrl,
  secondary = false,
  footerNote = null
}) => {
  return (
    <DataDisplayContainer>
      <H2 size="M">{title}</H2>
      {subTitle && (
        <StyledParagraph data-testid="data-usage-subtitle">
          {subTitle}
        </StyledParagraph>
      )}
      {data.length ? (
        <>
          <DataDisplayList data-testid={secondary ? 'secondary' : 'primary'}>
            {data.map(({ label, value }, index) => (
              <DataDisplayListItem key={index} secondary={secondary}>
                {value}
                <span>{label}</span>
              </DataDisplayListItem>
            ))}
          </DataDisplayList>
          {historyUrl && (
            <StyledParagraph>
              To see who has used this item,{' '}
              <Link href={historyUrl}>go to usage history</Link>
            </StyledParagraph>
          )}
        </>
      ) : (
        <StyledParagraph>Currently no data to display</StyledParagraph>
      )}
      {footerNote && (
        <StyledParagraph data-testid="data-display-footer-note">
          {footerNote}
        </StyledParagraph>
      )}
    </DataDisplayContainer>
  );
};

export default DataDisplay;
