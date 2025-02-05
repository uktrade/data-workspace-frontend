import { render } from '@testing-library/react';

import { TransformedYourRecentCollectionResponse } from '../../../../types';
import RecentCollections from '.';

describe('RecentCollections', () => {
  const collections: TransformedYourRecentCollectionResponse = [
    {
      name: 'Ians personal collection',
      url: '/collections/3d6111f8-ea21-42bc-9514-c3072caa8af0'
    },
    {
      name: 'Data Workspace feedback banner results',
      url: '/collections/4e9e91a6-b519-45f9-87a4-4e6bbedddbc2'
    },
    {
      name: 'Interactions and service deliveries for companies between 2010 and 2023',
      url: '/collections/fd135668-bebe-4270-aec3-067e525bdc50'
    }
  ];

  describe('With results', () => {
    it('should render a title', () => {
      const { getByRole } = render(
        <RecentCollections collections={collections} />
      );
      expect(
        getByRole('heading', { level: 2, name: 'Your recent collections' })
      );
    });
    it('should render a generic description', () => {
      const { getByText } = render(
        <RecentCollections collections={collections} />
      );
      expect(
        getByText(
          /In collections you can create a space for yourself and colleagues to share data, dashboards and notes./i
        )
      ).toBeInTheDocument();
    });
    it('should NOT render a no collections message', () => {
      const { queryByText } = render(
        <RecentCollections collections={collections} />
      );
      expect(
        queryByText(
          /You've currently not created a collection, or you're not a part of an existing collection./i
        )
      ).not.toBeInTheDocument();
    });
    it('should NOT render a link to create a collection', () => {
      const { queryByRole } = render(
        <RecentCollections collections={collections} />
      );
      expect(
        queryByRole('link', { name: 'Create a collection' })
      ).not.toBeInTheDocument();
    });

    it('should NOT render a link to find out more about collections', () => {
      const { queryByRole } = render(
        <RecentCollections collections={collections} />
      );
      expect(
        queryByRole('link', { name: 'Find out more about collections' })
      ).not.toBeInTheDocument();
    });
    it('should render a link to view all collections', () => {
      const { getByRole } = render(
        <RecentCollections collections={collections} />
      );
      expect(
        getByRole('link', { name: 'View all collections' })
      ).toHaveAttribute('href', '/collections');
    });
  });
  describe('No results', () => {
    it('should render a title', () => {
      const { getByRole } = render(<RecentCollections collections={[]} />);
      expect(
        getByRole('heading', { level: 2, name: 'Your recent collections' })
      );
    });
    it('should render a generic description', () => {
      const { getByText } = render(<RecentCollections collections={[]} />);
      expect(
        getByText(
          /In collections you can create a space for yourself and colleagues to share data, dashboards and notes./i
        )
      ).toBeInTheDocument();
    });
    it('should render a no collections message', () => {
      const { getByText } = render(<RecentCollections collections={[]} />);
      expect(
        getByText(
          /You've currently not created a collection, or you're not a part of an existing collection./i
        )
      ).toBeInTheDocument();
    });
    it('should render a link to create a collection', () => {
      const { getByRole } = render(<RecentCollections collections={[]} />);
      expect(
        getByRole('link', { name: 'Create a collection' })
      ).toHaveAttribute('href', '/collections/create');
    });
    it('should render a link to find out more about collections', () => {
      const { getByRole } = render(<RecentCollections collections={[]} />);
      expect(
        getByRole('link', { name: 'Find out more about collections' })
      ).toHaveAttribute(
        'href',
        'https://data-services-help.trade.gov.uk/data-workspace/how-to/start-using-data-workspace/collections/'
      );
    });
  });
});
