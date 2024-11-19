import React, { useState } from 'react';

import { Button } from '@govuk-react/button';
import Table from '@govuk-react/table';
import { Paragraph } from 'govuk-react';
import styled from 'styled-components';

import ConfirmDialog from '../../components/ConfirmDialog/';

const SpanBold = styled('span')`
  font-weight: bold;
`;

type User = {
  data_catalogue_editor: boolean;
  email: string;
  first_name: string;
  iam: boolean;
  iao: boolean;
  id: string;
  last_name: string;
  remove_user_url: string;
};

const UserTypeSuffix: React.FC<Record<'user', User>> = function ({ user }) {
  let user_type_suffix = '';
  if (user.iam) {
    user_type_suffix = '(Information Asset Manager)';
  } else if (user.iao) {
    user_type_suffix = '(Information Asset Owner)';
  }
  return <>{user_type_suffix}</>;
};

const ConfirmRemoveUser = ({
  data
}: {
  data: Array<User>;
}): React.ReactNode => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const closeModal = () => {
    setIsOpen(false);
    setSelectedUser(null);
  };
  const openModal = (user: User) => {
    setSelectedUser(user);
    setIsOpen(true);
  };
  return (
    <>
      {data.length && (
        <div>
          <Table>
            {data.map((user) => (
              <Table.Row key={user.id}>
                <Table.Cell style={{ paddingBottom: '1px' }}>
                  <SpanBold>{`${user.first_name} ${user.last_name} `}</SpanBold>
                  <UserTypeSuffix user={user} />
                  <Paragraph>{user.email}</Paragraph>
                </Table.Cell>
                {[user.iam, user.iao].some((x) => x == true) ? (
                  <Table.Cell></Table.Cell>
                ) : (
                  <Table.Cell
                    style={{
                      verticalAlign: 'middle',
                      textAlign: 'right'
                    }}
                  >
                    <Button
                      buttonColour="#f3f2f1"
                      buttonTextColour="#0b0c0c"
                      onClick={() => openModal(user)}
                      style={{ marginBottom: 0 }}
                    >
                      Remove User
                    </Button>
                  </Table.Cell>
                )}
              </Table.Row>
            ))}
          </Table>
        </div>
      )}
      {isOpen && selectedUser && (
        <ConfirmDialog
          actionUrl={selectedUser.remove_user_url}
          title={`Are you sure you want to remove ${selectedUser?.first_name} ${selectedUser?.last_name}'s access to this data?`}
          open={isOpen}
          onClose={closeModal}
          buttonText={'Yes, remove user'}
        ></ConfirmDialog>
      )}
    </>
  );
};

export default ConfirmRemoveUser;
