import React, { useState } from 'react';

import { Button } from '@govuk-react/button';
import { ListItem, Paragraph, UnorderedList } from 'govuk-react';
import styled from 'styled-components';

import ConfirmDialog from '../../components/ConfirmDialog';
import { ERROR_COLOUR } from '../../constants';

const StyledParagraph = styled(Paragraph)`
  padding-top: 30px;
`;

type unpublishDataType = {
  unpublish_url: string;
};

const UnpublishCataloguePage = ({
  data
}: {
  data: unpublishDataType;
}): React.ReactNode => {
  const csrf_token = document.cookie
    .split(';')
    .find((c) => c.trim().includes('data_workspace_csrf='))
    ?.split('=')
    ?.slice(-1)[0] as string;
  const [isOpen, setIsOpen] = useState(false);
  const closeModal = () => {
    setIsOpen(false);
  };
  const openModal = () => {
    setIsOpen(true);
  };
  return (
    <>
      <Button
        buttonColour="#f3f2f1"
        buttonTextColour="#0b0c0c"
        onClick={() => openModal()}
      >
        {'Unpublish catalogue page'}
      </Button>
      {isOpen && (
        <ConfirmDialog
          actionUrl={data.unpublish_url}
          csrf_token={csrf_token}
          title="Final review before unpublishing"
          open={isOpen}
          onClose={closeModal}
          buttonTextAccept="Yes, unpublish catalogue page"
          buttonColourAccept={ERROR_COLOUR}
          buttonTextCancel={'Close'}
          buttonValueAccept="unpublish-catalogue"
          warning={true}
        >
          <>
            <StyledParagraph>
              By clicking the 'Yes' button below you're confirmimg:
            </StyledParagraph>
            <UnorderedList>
              <ListItem>
                <Paragraph>
                  this catalogue page needs to be unpublished because of a
                  potential data breach
                </Paragraph>
              </ListItem>
              <ListItem>
                <Paragraph>
                  you understand that any data linked to this catalogue page
                  will also be removed
                </Paragraph>
              </ListItem>
            </UnorderedList>
          </>
        </ConfirmDialog>
      )}
    </>
  );
};

export default UnpublishCataloguePage;
