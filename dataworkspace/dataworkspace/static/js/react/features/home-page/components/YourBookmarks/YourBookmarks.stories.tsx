import type { Meta, StoryObj } from '@storybook/react';

import type { YourBookmarksProps } from '.';
import YourBookmarks from '.';

const meta = {
    title: 'Your Bookmarks',
    component: YourBookmarks
} satisfies Meta<typeof YourBookmarks>;

type Story = StoryObj<typeof YourBookmarks>;

const bookmarks: YourBookmarksProps[] = [
    {
        url: '/some-url',
        name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
    },
    {
        url: '/some-url',
        name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
    },
    {
        url: '/some-url',
        name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
    },
    {
        url: '/some-url',
        name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
    },
    {
        url: '/some-url',
        name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
    },
];

export const withBookmarks: Story = {
    render: () => <YourBookmarks bookmarks={bookmarks} />
};

export const noBookmarks: Story = {
    render: () => <YourBookmarks bookmarks={[]} />
};

export default meta;