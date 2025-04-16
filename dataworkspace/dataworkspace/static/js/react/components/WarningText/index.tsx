import * as React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import styled from 'styled-components';

import IconImportant from './IconImportant';

const StyledWarningText = styled('div')({
  alignItems: 'center',
  boxSizing: 'border-box',
  display: 'flex',
  width: '100%'
});

const IconImportantWrapper = styled('div')({
  flex: 'none',
  width: 35,
  height: 35,
  marginRight: SPACING_POINTS[3]
});

const WarningTextWrapper = styled('strong')(
  typography.font({ size: 19, weight: 'bold' })
);

export const WarningText: React.FC<WarningTextProps> = ({
  children,
  ...props
}: WarningTextProps) => (
  <StyledWarningText {...props}>
    <IconImportantWrapper>
      <IconImportant />
    </IconImportantWrapper>
    <WarningTextWrapper>{children}</WarningTextWrapper>
  </StyledWarningText>
);

WarningText.displayName = 'WarningText';

export interface WarningTextProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export default WarningText;
