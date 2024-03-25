import { SPACING } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import type { Meta, StoryObj } from '@storybook/react';
import styled from 'styled-components';

import Tile from './index';

const StyledParagraph = styled('p')`
  margin: ${SPACING.SCALE_3} 0;
  ${typography.font({ size: 19 })};
`;

const meta = {
  title: 'Tile',
  component: Tile
} satisfies Meta<typeof Tile>;

type Story = StoryObj<typeof Tile>;

export const WithContent: Story = {
  render: () => (
    <Tile title="Tile">
      <StyledParagraph>
        Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
        tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim
        veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea
        commodo consequat.
      </StyledParagraph>
    </Tile>
  )
};

export default meta;
