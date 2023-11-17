import React, { ReactNode } from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { H3 } from 'govuk-react';
import styled from 'styled-components';

import { MID_GREY, WHITE } from '../../constants';

const TileStyling = styled('div')`
  padding: ${SPACING_POINTS['4']}px;
  border: 1px solid ${MID_GREY};
  background-color: ${WHITE};
`;

interface TileProps {
  title: string;
  children: ReactNode;
}

const Tile: React.FC<TileProps> = ({ title, children }) => {
  return (
    <TileStyling>
      <H3 size={27}>{title}</H3>
      {children}
    </TileStyling>
  );
};

export default Tile;
