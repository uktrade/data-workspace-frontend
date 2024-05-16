import Button from '@govuk-react/button';
import Checkbox from '@govuk-react/checkbox';
import { H3 } from '@govuk-react/heading';

import type { PostFeedback } from './index';

export const mockPostFeedback: PostFeedback = () => {
  return new Promise((resolve) => {
    setTimeout(resolve);
  });
};

export const mockRejectPostFeedback: PostFeedback = () => {
  return new Promise((_resolve, reject) =>
    setTimeout(reject, 0, 'Oh no something went wrong!')
  );
};

export const ChildForm = ({
  location,
  wasItHelpful
}: {
  location: string;
  wasItHelpful: boolean;
}) => {
  return (
    <form>
      {wasItHelpful ? (
        <>
          <H3 size="SMALL">
            Thats great. Can you tell us more about the {location} page?
            (optional)
          </H3>
          <Checkbox name="option">Yes option 1</Checkbox>
          <Checkbox name="option">Yes option 2</Checkbox>
        </>
      ) : (
        <>
          <H3 size="SMALL">
            Sorry to hear about that. How can we help make the {location} page
            better? (optional)
          </H3>
          <Checkbox name="option">No option 1</Checkbox>
          <Checkbox name="option">No option 2</Checkbox>
        </>
      )}
      <br />
      <Button>Submit</Button>
    </form>
  );
};
