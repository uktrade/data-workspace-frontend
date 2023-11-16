import { render } from '@testing-library/react';

import SupportYou from './SupportYou';

describe('SupportYou', () => {
    it('renders a H2 header', () => {
        const { getByRole } = render(<SupportYou/>);
        const header = getByRole('heading', { level: 2, name: 'How can we support you?' });
        expect(header).toBeInTheDocument();
    });
    it('renders TilesContainer with GetHelp and OtherSupport components', () => {
        const { queryAllByRole } = render(<SupportYou />);
        const headers = queryAllByRole('heading', { level: 3 });
        expect(headers.length).toBe(2);
    });
});
