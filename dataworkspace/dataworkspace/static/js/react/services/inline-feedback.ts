import { API_BASE_URL } from '../constants';

export type FeedbackResponse = {
  id: string;
  location: string;
  was_this_page_helpful: boolean;
  inline_feedback_choices: string | null;
  more_detail: string | null;
};

const handleResponse = async <T extends object>(response: Response) => {
  if (!response.ok) {
    throw `${response.status} ${response.statusText}`;
  }
  const responseData: T = await response.json();
  return responseData;
};

export const postFeedback = async (
  csrf_token: string,
  location: string,
  wasItHelpful: boolean
): Promise<FeedbackResponse> => {
  const response = await fetch(`${API_BASE_URL}/inline_feedback`, {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf_token
    },
    method: 'POST',
    body: JSON.stringify({
      was_this_page_helpful: wasItHelpful,
      location
    })
  });
  return handleResponse<FeedbackResponse>(response);
};

export const patchFeedback = async (
  csrf_token: string,
  id: string,
  payload: { inline_feedback_choices: string; more_detail: string }
): Promise<FeedbackResponse> => {
  const response = await fetch(`${API_BASE_URL}/inline_feedback/${id}`, {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf_token
    },
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
  return handleResponse<FeedbackResponse>(response);
};
