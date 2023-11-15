import React from 'react';

import { render } from '@testing-library/react';

import Tile from '.';

const TestComponent: React.FC = () => {
    return <p>Test Content</p>;
};

describe('Tile', () => {
    it('renders with test content', () => {
        const { getByText } = render(<Tile title="Test Title"><TestComponent /></Tile>);
        expect(getByText('Test Title')).toBeInTheDocument();
        expect(getByText('Test Content')).toBeInTheDocument();
    });
});
