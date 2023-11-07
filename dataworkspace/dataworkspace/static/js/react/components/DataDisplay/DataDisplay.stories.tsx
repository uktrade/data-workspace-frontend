import type { Meta, StoryObj } from '@storybook/react';

import type { TransformedDataUsageResponse } from '../../types/dataUsage.types';
import { DataDisplay } from '../index';

const meta = {
  title: 'Data usage',
  component: DataDisplay
} satisfies Meta<typeof DataDisplay>;

const primaryData = [
  {
    label: 'Dashboard views',
    value: 100
  },
  {
    label: 'Bookmarked by users',
    value: 200
  },
  {
    label: 'Average daily users',
    value: 0.25
  },
  {
    label: 'Table views',
    value: 25
  },
  {
    label: 'Added to collections',
    value: 4
  }
] as TransformedDataUsageResponse[];

const secondaryData = [
  {
    label: 'Page views',
    value: 100
  },
  {
    label: 'Added to collections',
    value: 200
  },
  {
    label: 'Dashboard views',
    value: 25
  },
  {
    label: 'Bookmarked by users',
    value: 25
  }
] as TransformedDataUsageResponse[];

type Story = StoryObj<typeof DataDisplay>;

export const WithData: Story = {
  render: () => (
    <DataDisplay
      data={primaryData}
      subTitle="The data below has been captured since this catalogue item was initially published."
    />
  )
};

export const NoData: Story = {
  render: () => (
    <DataDisplay
      data={[]}
      subTitle="The data below has been captured since this catalogue item was initially published."
    />
  )
};

export const SecondaryLayout: Story = {
  render: () => (
    <DataDisplay
      data={secondaryData}
      secondary
      subTitle="The data below has been captured since this catalogue item was initially published."
    />
  )
};

export default meta;
