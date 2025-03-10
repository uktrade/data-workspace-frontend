import React, { useState } from 'react';

import { Button } from '@govuk-react/button';

import ConfirmDialog from '../../components/ConfirmDialog/';

type publishData = {
  csrf_token: string;
  is_catalogue: boolean; // or visualisation
};

const ConfirmPublishVisualisation = ({
  data
}: {
  data: publishData;
}): React.ReactNode => {
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
        {data.is_catalogue ? 'Publish catalogue page' : 'Release to production'}
      </Button>
      {isOpen && (
        <ConfirmDialog
          actionUrl={''}
          bodyText={
            'You‘re responsible for the information security and data protection of the data this visualisation uses. All data must be published to the Data Workspace catalogue. Storing and using data from Gitlab is not permitted.'
          }
          csrf_token={data.csrf_token}
          title={
            data.is_catalogue
              ? 'Final review before publishing'
              : 'Final review before releasing to production'
          }
          open={isOpen}
          onClose={closeModal}
          buttonTextAccept={
            data.is_catalogue ? 'Publish to catalogue' : 'Release to production'
          }
          buttonTextCancel={'Close'}
          buttonValueAccept={
            data.is_catalogue ? 'publish-catalogue' : 'publish-visualisation'
          }
          warning={true}
        ></ConfirmDialog>
      )}
    </>
  );
};

export default ConfirmPublishVisualisation;
