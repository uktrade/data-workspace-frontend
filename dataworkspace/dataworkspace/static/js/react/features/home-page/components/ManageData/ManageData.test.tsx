import { render } from '@testing-library/react';

import { ManagedDataResponse } from '../../../../types';
import ManagedData from '.';

describe('RecentCollections', () => {
  const managed_data_stats_multiple_datasets: ManagedDataResponse = {
    count: 5,
    managed_data_url: '/datasets?q='
  };

  const managed_data_stats_single_dataset: ManagedDataResponse = {
    count: 1,
    managed_data_url: '/datasets?q='
  };

  const managed_data_stats_no_dataset: ManagedDataResponse = {
    count: 0,
    managed_data_url: '/datasets?q='
  };

  describe('With results', () => {
    it('should render a title', () => {
      const { getByRole } = render(
        <ManagedData
          managed_data_stats={managed_data_stats_multiple_datasets}
        />
      );
      expect(
        getByRole('heading', {
          level: 2,
          // eslint-disable-next-line quotes
          name: "You're the owner or manager of 5 datasets"
        })
      );
    });
    it('should render a title in the singular', () => {
      const { getByRole } = render(
        <ManagedData managed_data_stats={managed_data_stats_single_dataset} />
      );
      expect(
        getByRole('heading', {
          level: 2,
          // eslint-disable-next-line quotes
          name: "You're the owner or manager of 1 dataset"
        })
      );
    });
    it('should not render at all', () => {
      const { queryByRole } = render(
        <ManagedData managed_data_stats={managed_data_stats_no_dataset} />
      );
      expect(
        queryByRole('heading', {
          level: 2,
          // eslint-disable-next-line quotes
          name: "You're the owner or manager of 0 dataset"
        })
      ).not.toBeInTheDocument();
    });
    it('should render a link to the manage data page', () => {
      const { getByRole } = render(
        <ManagedData managed_data_stats={managed_data_stats_single_dataset} />
      );
      expect(
        getByRole('link', { name: 'View and manage your data' })
      ).toHaveAttribute('href', '/datasets?q=');
    });
    it('should render a link to helpcentre guidance', () => {
      const { getByRole } = render(
        <ManagedData managed_data_stats={managed_data_stats_single_dataset} />
      );
      expect(
        getByRole('link', {
          // eslint-disable-next-line quotes
          name: "Learn how to maintain and manage data you're responsible for on Data Workspace"
        })
      ).toHaveAttribute(
        'href',
        'https://data-services-help.trade.gov.uk/data-workspace/add-share-and-manage-data/manage-data/'
      );
    });
    it('should not render a link to helpcentre guidance', () => {
      const { queryByRole } = render(
        <ManagedData managed_data_stats={managed_data_stats_no_dataset} />
      );
      expect(
        queryByRole('link', {
          // eslint-disable-next-line quotes
          name: "Learn how to maintain and manage data you're responsible for on Data Workspace"
        })
      ).not.toBeInTheDocument();
    });
  });
});
