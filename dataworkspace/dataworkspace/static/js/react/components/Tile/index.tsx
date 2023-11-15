import React, { ReactNode } from 'react';

import {
    SPACING_POINTS
  } from '@govuk-react/constants';
import { H2 } from 'govuk-react';
import styled from 'styled-components';

const TileStyling = styled('div')`
    padding:${SPACING_POINTS['6']}px;
    border: 1px solid #b1b4b6;
    background-color: #ffffff;
`;

interface TileProps {
    title: string;
    children: ReactNode;
}

const Tile: React.FC<TileProps> = ({ 
    title, 
    children
}) => {
    return (
        <TileStyling>
            <H2 size={27}>{title}</H2>
            {children}
        </TileStyling>
    );
};

export default Tile;
