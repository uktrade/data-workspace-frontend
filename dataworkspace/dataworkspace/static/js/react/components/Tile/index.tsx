import React, { ReactNode } from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { H1, H2, H3, H4, H5 } from 'govuk-react';
import styled from 'styled-components';

import { MID_GREY, WHITE } from '../../constants';

const InnerContainer = styled('div')`
  padding: ${SPACING_POINTS['4']}px;
  border: 1px solid ${MID_GREY};
  background-color: ${WHITE};
`;

type TileProps = {
  title: string;
  as?: React.ElementType;
  headerSize?: number;
  headerLevel?: 1 | 2 | 3 | 4 | 5;
  children: ReactNode;
  dataTest?: string;
};

type HeaderProps = Pick<TileProps, 'headerSize' | 'headerLevel' | 'children'>;

const Header: React.FC<HeaderProps> = ({
  headerLevel = 2,
  headerSize,
  children
}) => {
  const header: Record<number, React.ReactNode> = {
    [1]: <H1 size={headerSize}>{children}</H1>,
    [2]: <H2 size={headerSize}>{children}</H2>,
    [3]: <H3 size={headerSize}>{children}</H3>,
    [4]: <H4 size={headerSize}>{children}</H4>,
    [5]: <H5 size={headerSize}>{children}</H5>
  };
  return header[headerLevel];
};

const Tile: React.FC<TileProps> = ({
  title,
  headerSize = 27,
  headerLevel = 2,
  as,
  children,
  dataTest
}) => {
  const Component = as || 'div';
  return (
    <Component data-test={dataTest}>
      <InnerContainer>
        <Header headerLevel={headerLevel} headerSize={headerSize}>
          {title}
        </Header>
        {children}
      </InnerContainer>
    </Component>
  );
};

export default Tile;
