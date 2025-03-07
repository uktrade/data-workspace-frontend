import React, { useState } from 'react';

import { Button } from '@govuk-react/button';

import ConfirmDialog from '../../components/ConfirmDialog/';

type publishData = {
  publish_action: string;
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
        Publish Visualisation
      </Button>
      {isOpen && (
        <ConfirmDialog
          actionUrl={data.publish_action}
          bodyText={
            'You‘re responsible for the information security and data protection of the data this visualisation uses. All data must be published to the Data Workspace catalogue. Storing and using data from Gitlab is not permitted.'
          }
          title={'Final review before publishing'}
          open={isOpen}
          onClose={closeModal}
          buttonTextAccept={'Publish to catalogue'}
          buttonTextCancel={'Close'}
          warning={true}
        ></ConfirmDialog>
      )}
    </>
  );
};

export default ConfirmPublishVisualisation;
