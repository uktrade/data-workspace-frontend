import React, { useState } from 'react';

import { Button } from '@govuk-react/button';

import ConfirmDialog from '../../components/ConfirmDialog';

type unpublishDataType = {
  unpublish_url: string; // or visualisation
};

const UnpublishCataloguePage = ({ data }: {
  data: unpublishDataType;
}): React.ReactNode => {
  console.log(data)
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
          bodyText={
            'You‘re responsible for the information security and data protection of the data this visualisation uses. All data must be published to the Data Workspace catalogue. Storing and using data from Gitlab is not permitted.'
          }
          csrf_token={csrf_token}
          // title={
          //   data.unpublish_url
          //     ? 'Final review before publishing'
          //     : 'Final review before releasing to production'
          // }
          title="Unpublishe catalogue"
          open={isOpen}
          onClose={closeModal}
          // buttonTextAccept={
          //   data.unpublish_url
          //     ? 'Publish to catalogue'
          //     : 'Release to production'
          // }
          buttonTextAccept="Unpublish catalogue"
          buttonTextCancel={'Close'}
          // buttonValueAccept={
          //   data.unpublish_url ? 'publish-catalogue' : 'publish-visualisation'
          // }
          buttonValueAccept="unpublish-catalogue"
          warning={true}
        ></ConfirmDialog>
      )}
    </>
  );
};

export default UnpublishCataloguePage;
