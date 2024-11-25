import type { Meta, StoryObj } from '@storybook/react';

import type { ManagedDataProps } from '.';
import ManagedData from '.';

const MultipleDatasets: ManagedDataProps[] = [
  {
    count: 5,
    managed_data_url: '/datasets?q='
  }
];

const SingularDataset: ManagedDataProps[] = [
  {
    count: 1,
    managed_data_url: '/datasets?q='
  }
];

const NoDatasets: ManagedDataProps[] = [
  {
    count: 0,
    managed_data_url: '/datasets?q='
  }
];

const meta = {
  title: 'Managed Data',
  component: ManagedData
} satisfies Meta<typeof ManagedData>;

type Story = StoryObj<typeof ManagedData>;

export const withMultipleDatasets: Story = {
  render: () => <ManagedData managed_data_stats={MultipleDatasets} />
};

export const withSingleDatasets: Story = {
  render: () => <ManagedData managed_data_stats={SingularDataset} />
};

export const noDatasets: Story = {
  render: () => <ManagedData managed_data_stats={NoDatasets} />
};

export default meta;
