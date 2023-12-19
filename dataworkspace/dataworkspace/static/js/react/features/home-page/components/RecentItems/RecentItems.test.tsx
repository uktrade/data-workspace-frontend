import { render } from '@testing-library/react';

import type { RecentItemProps } from '.';
import RecentItems from '.';

const items: RecentItemProps[] = [
  {
    url: '/url-1',
    name: 'Title 1'
  },
  {
    url: '/url-2',
    name: 'Title 2'
  }
];

describe('RecentItems', () => {
  describe('With results', () => {
    it('should render a title', () => {
      const { getByRole } = render(<RecentItems items={items} />);
      expect(getByRole('heading', { level: 2, name: 'Your recent items' }));
    });
    it('should render generic content', () => {
      const { getByText } = render(<RecentItems items={items} />);
      expect(
        getByText(
          'This might be a Source dataset, Reference dataset, Data cut, or Visualisation.'
        )
      ).toBeInTheDocument();
    });
    it('should render a list of links', () => {
      const { queryAllByRole, getByRole } = render(
        <RecentItems items={items} />
      );
      expect(queryAllByRole('listitem')).toHaveLength(2);
      expect(getByRole('link', { name: 'Title 1' })).toHaveAttribute(
        'href',
        '/url-1'
      );
      expect(getByRole('link', { name: 'Title 2' })).toHaveAttribute(
        'href',
        '/url-2'
      );
    });
    it('should NOT render content for new users', () => {
      const { queryByRole, queryByText } = render(
        <RecentItems items={items} />
      );
      expect(
        queryByText(/You have not searched anything yet. Use the/i)
      ).not.toBeInTheDocument();
      expect(
        queryByText(/To find out more about what catalogue items are/i)
      ).not.toBeInTheDocument();
      expect(
        queryByRole('link', { name: 'Data types on Data Workspace' })
      ).not.toBeInTheDocument();
    });
  });
  describe('No results', () => {
    it('should render a title', () => {
      const { getByRole } = render(<RecentItems items={[]} />);
      expect(getByRole('heading', { level: 2, name: 'Your recent items' }));
    });
    it('should render generic content', () => {
      const { getByText } = render(<RecentItems items={[]} />);
      expect(
        getByText(
          'This might be a Source dataset, Reference dataset, Data cut, or Visualisation.'
        )
      ).toBeInTheDocument();
    });
    it('should NOT render a list of links', () => {
      const { queryAllByRole, queryByRole } = render(
        <RecentItems items={[]} />
      );
      expect(queryAllByRole('listitem')).toHaveLength(0);
      expect(queryByRole('link', { name: 'Title 1' })).not.toBeInTheDocument();
      expect(queryByRole('link', { name: 'Title 2' })).not.toBeInTheDocument();
    });
    it('should render content for new users', () => {
      const { getByText, getByRole } = render(<RecentItems items={[]} />);
      expect(
        getByText(/You have not searched anything yet. Use the/i)
      ).toBeInTheDocument();
      expect(
        getByText(/To find out more about what catalogue items are/i)
      ).toBeInTheDocument();
      expect(
        getByRole('link', { name: 'Data types on Data Workspace' })
      ).toHaveAttribute(
        'href',
        'https://data-services-help.trade.gov.uk/data-workspace/policies-and-standards/standards/data-types/'
      );
    });
  });
});
