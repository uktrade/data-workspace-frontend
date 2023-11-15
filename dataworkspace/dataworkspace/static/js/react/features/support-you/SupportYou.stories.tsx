import type { Meta, StoryObj } from '@storybook/react';

import SupportYou from './SupportYou';

const meta = {
    title: 'Support You feature',
    component: SupportYou
} satisfies Meta<typeof SupportYou>;

type Story = StoryObj<typeof SupportYou>

export const WithTiles: Story = {
    render: () => (
        <SupportYou />
    ),
};

export default meta;
