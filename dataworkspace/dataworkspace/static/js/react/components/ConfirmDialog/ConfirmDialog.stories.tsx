// @ts-ignore
import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';
import { ListItem, Paragraph, UnorderedList } from 'govuk-react';
import styled from 'styled-components';

import { ERROR_COLOUR } from '../../constants';
import { ConfirmDialog } from './index';

const meta = {
  title: 'ConfirmRemoveDialog',
  component: ConfirmDialog
} satisfies Meta<typeof ConfirmDialog>;

type Story = StoryObj<typeof ConfirmDialog>;

const StyledParagraph = styled(Paragraph)`
  padding-top: 30px;
`;

export const ConfirmRemoveUser: Story = {
  render: () => (
    <ConfirmDialog
      actionUrl="/submit"
      buttonValueAccept='""'
      bodyText='""'
      buttonTextAccept="Remove User?"
      buttonTextCancel="Cancel"
      csrf_token="123"
      onClose={() => {}}
      open={true}
      title="Are you sure you want to remove Jones?"
      warning={false}
    />
  )
};

export const ConfirmCustomBody: Story = {
  render: () => (
    <ConfirmDialog
      actionUrl="/submit-team"
      buttonValueAccept='""'
      buttonTextAccept="Yes"
      buttonTextCancel="Cancel"
      buttonColourAccept={ERROR_COLOUR}
      csrf_token="456"
      onClose={() => {}}
      open={true}
      title="Are you sure you want to unpublish the catalogue"
      warning={true}
    >
      <>
        <StyledParagraph>
          By clicking the 'Yes' button below you're confirming:
        </StyledParagraph>
        <UnorderedList>
          <ListItem>
            this catalogue page needs to be unpublished because of a potential
            data breach
          </ListItem>
          <ListItem>
            you understand that any data linked to this catalogue page will also
            be removed
          </ListItem>
        </UnorderedList>
      </>
    </ConfirmDialog>
  )
};

export default meta;
