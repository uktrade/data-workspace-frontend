import { render } from '@testing-library/react';

import type { RecentToolsProps } from '.';
import RecentTools from '.';

const tools: RecentToolsProps[] = [
  {
    url: '/url-1',
    title: 'Tool 1'
  },
  {
    url: '/url-2',
    title: 'Tool 2'
  }
];

describe('RecentTools', () => {
  describe('with tools', () => {
    it('should display a title', () => {
      const { getByRole } = render(<RecentTools tools={tools} />);
      expect(getByRole('heading', { level: 3, name: 'Your recent tools' }));
    });
    it('should render generic content', () => {
      const { getByText } = render(<RecentTools tools={tools} />);
      expect(
        getByText('We have a range of tools you can use with datasets.')
      ).toBeInTheDocument();
    });
    it('should render recent tool links', () => {
      const { getByRole } = render(<RecentTools tools={tools} />);
      expect(getByRole('link', { name: 'Tool 1' })).toHaveAttribute(
        'href',
        '/url-1'
      );
      expect(getByRole('link', { name: 'Tool 2' })).toHaveAttribute(
        'href',
        '/url-2'
      );
    });
    it('should render a link to view all tools', () => {
      const { getByRole } = render(<RecentTools tools={tools} />);
      expect(getByRole('link', { name: 'View all tools' })).toHaveAttribute(
        'href',
        '/tools'
      );
    });
    it('should NOT render guidance content on how to start using tools', () => {
      const { queryByText, queryByRole } = render(
        <RecentTools tools={tools} />
      );
      expect(
        queryByText('You have not used a tool yet.')
      ).not.toBeInTheDocument();
      expect(
        queryByText(
          'To start using tools, click on the tools navigation item in the header or'
        )
      ).not.toBeInTheDocument();
      expect(
        queryByRole('link', { name: 'Find out more about tools' })
      ).not.toBeInTheDocument();
    });
  });
  describe('without tools', () => {
    it('should display a title', () => {
      const { getByRole } = render(<RecentTools tools={[]} />);
      expect(getByRole('heading', { level: 3, name: 'Your recent tools' }));
    });
    it('should render generic content', () => {
      const { getByText } = render(<RecentTools tools={[]} />);
      expect(
        getByText('We have a range of tools you can use with datasets.')
      ).toBeInTheDocument();
    });
    it('should NOT render recent tool links', () => {
      const { queryByRole } = render(<RecentTools tools={[]} />);
      expect(queryByRole('link', { name: 'Tool 1' })).not.toBeInTheDocument();
      expect(queryByRole('link', { name: 'Tool 2' })).not.toBeInTheDocument();
    });
    it('should NOT render a link to view all tools', () => {
      const { queryByRole } = render(<RecentTools tools={[]} />);
      expect(
        queryByRole('link', { name: 'View all tools' })
      ).not.toBeInTheDocument();
    });
    it('should render guidance content on how to start using tools', () => {
      const { getByText, getByRole } = render(<RecentTools tools={[]} />);
      expect(getByText('You have not used a tool yet.')).toBeInTheDocument();
      expect(
        getByText(
          'To start using tools, click on the ‘tools’ navigation item in the header or'
        )
      ).toBeInTheDocument();
      expect(
        getByRole('link', { name: 'Find out more about tools' })
      ).toHaveAttribute(
        'href',
        'https://data-services-help.trade.gov.uk/data-workspace/how-to/use-tools/about-data-workspace-tools/'
      );
    });
  });
});
