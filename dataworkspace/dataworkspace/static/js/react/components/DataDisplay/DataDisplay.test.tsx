import { render } from '@testing-library/react';

import { TransformedDataUsageResponse } from '../../types/index';
import DataDisplay from '.';

const data: TransformedDataUsageResponse = [
  {
    label: 'Dashboard views',
    value: 100
  },
  {
    label: 'Bookmarked by users',
    value: 200
  }
];
describe('Data display', () => {
  it('should render a default title', () => {
    const { getByRole } = render(<DataDisplay data={data} />);
    expect(getByRole('heading', { level: 3, name: 'Data usage' }));
  });
  it('should render a custom title', () => {
    const { getByRole } = render(
      <DataDisplay data={data} title="Custom title" />
    );
    expect(getByRole('heading', { level: 3, name: 'Custom title' }));
  });
  it('should render a sub title', () => {
    const { getByTestId } = render(
      <DataDisplay data={data} subTitle="Sub title" />
    );
    expect(getByTestId('data-usage-subtitle')).toBeInTheDocument();
  });
  it('should NOT render a sub title', () => {
    const { queryByTestId } = render(<DataDisplay data={data} />);
    expect(queryByTestId('data-usage-subtitle')).not.toBeInTheDocument();
  });
  it('should render a primary layout', () => {
    const { getByTestId } = render(<DataDisplay data={data} />);
    expect(getByTestId('primary')).toBeInTheDocument();
  });
  it('should render a secondary layout', () => {
    const { getByTestId } = render(<DataDisplay data={data} secondary />);
    expect(getByTestId('secondary')).toBeInTheDocument();
  });
  it('should display data', () => {
    const { getByText } = render(<DataDisplay data={data} />);
    expect(getByText('Dashboard views')).toBeInTheDocument();
    expect(getByText('100')).toBeInTheDocument();
    expect(getByText('Bookmarked by users')).toBeInTheDocument();
    expect(getByText('200')).toBeInTheDocument();
  });
  it('should NOT display data', () => {
    const { getByText } = render(<DataDisplay data={[]} />);
    expect(getByText('Currently no data to display')).toBeInTheDocument();
  });
  it('should display a message if no data is returned', () => {
    const { getByText } = render(<DataDisplay data={[]} />);
    expect(getByText('Currently no data to display')).toBeInTheDocument();
  });
  it('should NOT display a footer note', () => {
    const { queryByTestId } = render(<DataDisplay data={data} />);
    expect(queryByTestId('data-display-footer-note')).not.toBeInTheDocument();
  });
  it('should display a footer note', () => {
    const { queryByTestId, getByText } = render(
      <DataDisplay data={data} footerNote={<>Some footer note</>} />
    );
    expect(queryByTestId('data-display-footer-note')).toBeInTheDocument();
    expect(getByText('Some footer note')).toBeInTheDocument();
  });
});
