import type { Meta, StoryObj } from '@storybook/react';

import OtherSupport from '.';

const meta = {
    title: 'Other Ways of Support tile'
} satisfies Meta<typeof OtherSupport>;

type Story = StoryObj<typeof OtherSupport>

export const WithContent: Story = {
    render: () => (
        <OtherSupport />
    ),
};

export default meta;
