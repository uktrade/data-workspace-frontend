import React from 'react';

import { render } from '@testing-library/react';

import Tile from '.';

const TestComponent: React.FC = () => {
  return <p>Test Content</p>;
};

describe('Tile', () => {
  it('renders with test content', () => {
    const { getByRole, getByText } = render(
      <Tile title="Test Title">
        <TestComponent />
      </Tile>
    );
    const header = getByRole('heading', { level: 2, name: 'Test Title' });
    const content = getByText('Test Content');
    expect(header).toBeInTheDocument();
    expect(content).toBeInTheDocument();
  });
});
