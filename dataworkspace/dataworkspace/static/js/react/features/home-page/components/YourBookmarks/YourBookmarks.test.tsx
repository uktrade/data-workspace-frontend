import { render } from '@testing-library/react';

import type { YourBookmarksProps } from '.';
import YourBookmarks from '.';

const bookmarks: YourBookmarksProps[] = [
  {
    name: 'Bookmark 1',
    url: '/bookmark-1'
  },
  {
    name: 'Bookmark 2',
    url: '/bookmark-2'
  }
];

describe('YourBookmarks', () => {
  describe('With bookmarks', () => {
    it('should render a title', () => {
      const { getByRole } = render(<YourBookmarks bookmarks={bookmarks} />);
      expect(getByRole('heading', { level: 2, name: 'Your bookmarks' }));
    });
    it('should render generic content', () => {
      const { getByText } = render(<YourBookmarks bookmarks={bookmarks} />);
      expect(
        getByText(
          'Bookmarks are easy ways for you to access data you regularly use quicker.'
        )
      ).toBeInTheDocument();
    });
    it('should render a list of links', () => {
      const { queryAllByRole, getByRole } = render(
        <YourBookmarks bookmarks={bookmarks} />
      );
      expect(queryAllByRole('listitem')).toHaveLength(2);
      expect(getByRole('link', { name: 'Bookmark 1' })).toHaveAttribute(
        'href',
        '/bookmark-1'
      );
      expect(getByRole('link', { name: 'Bookmark 2' })).toHaveAttribute(
        'href',
        '/bookmark-2'
      );
    });
  });
  describe('No bookmarks', () => {
    it('should render a title', () => {
      const { getByRole } = render(<YourBookmarks bookmarks={bookmarks} />);
      expect(getByRole('heading', { level: 2, name: 'Your bookmarks' }));
    });
    it('should render generic content', () => {
      const { getByText } = render(<YourBookmarks bookmarks={[]} />);
      expect(
        getByText(
          'You do not have any bookmarks yet. When searching for data, select the bookmark icon to bookmark data.'
        )
      ).toBeInTheDocument();
    });
    it('should NOT render a list of links', () => {
      const { queryAllByRole, queryByRole } = render(
        <YourBookmarks bookmarks={[]} />
      );
      expect(queryAllByRole('listitem')).toHaveLength(0);
      expect(
        queryByRole('link', { name: 'Bookmark 1' })
      ).not.toBeInTheDocument();
      expect(
        queryByRole('link', { name: 'Bookmark 2' })
      ).not.toBeInTheDocument();
    });
  });
});
