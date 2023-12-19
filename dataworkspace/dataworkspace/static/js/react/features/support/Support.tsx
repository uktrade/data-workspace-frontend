import React from 'react';

import { MEDIA_QUERIES, SPACING_POINTS } from '@govuk-react/constants';
import { H2 } from 'govuk-react';
import styled from 'styled-components';

import { WHITE } from '../../constants';
import GetHelp from './components/GetHelp';
import GetInTouch from './components/GetInTouch';

const SupportContainer = styled('div')`
  background-color: ${WHITE};
`;

const TilesContainer = styled('div')`
  display: grid;
  grid-template-columns: 1fr;
  grid-gap: ${SPACING_POINTS[3]}px;
  ${MEDIA_QUERIES.TABLET} {
    grid-template-columns: repeat(2, 1fr);
    grid-gap: ${SPACING_POINTS[6]}px;
  }
`;

const SupportYou: React.FC = () => {
  return (
    <SupportContainer>
      <H2>How we can support you</H2>
      <TilesContainer>
        <GetHelp />
        <GetInTouch />
      </TilesContainer>
    </SupportContainer>
  );
};

export default SupportYou;
