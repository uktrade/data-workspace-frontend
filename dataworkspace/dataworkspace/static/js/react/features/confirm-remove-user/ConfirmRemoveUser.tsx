import React, { useState } from 'react';

import { Button } from '@govuk-react/button';
import { H2 } from '@govuk-react/heading';
import Table from '@govuk-react/table';
import { Paragraph } from 'govuk-react';
import styled from 'styled-components';

import ConfirmDialog from '../../components/ConfirmDialog/';

const RemoveUserTableCell = styled(Table.Cell)`
  vertical-align: middle;
  text-align: right;
`;

const SpanBold = styled('span')`
  font-weight: bold;
`;

const UserNameTableCell = styled(Table.Cell)`
  padding-bottom: 1px;
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

const populateUserTypeSuffix = function (user: User) {
  let user_type_suffix = '';
  if (user.iam) {
    user_type_suffix += '(Information Asset Manager) ';
  }
  if (user.iao) {
    user_type_suffix += '(Information Asset Owner)';
  }
  return user_type_suffix.trim();
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
      {data.length < 1 ? (
        <H2>There are currently no authorized users</H2>
      ) : (
        <div>
          <H2>Users who have access</H2>
          <Table>
            {data.map((user) => (
              <Table.Row key={user.id}>
                <UserNameTableCell>
                  <SpanBold>{`${user.first_name} ${user.last_name} `}</SpanBold>
                  {populateUserTypeSuffix(user)}
                  <Paragraph>{user.email}</Paragraph>
                </UserNameTableCell>
                {[user.iam, user.iao].some((x) => x == true) ? (
                  <Table.Cell></Table.Cell>
                ) : (
                  <RemoveUserTableCell>
                    <Button
                      buttonColour="#f3f2f1"
                      buttonTextColour="#0b0c0c"
                      onClick={() => openModal(user)}
                      style={{ marginBottom: 0 }}
                    >
                      Remove User
                    </Button>
                  </RemoveUserTableCell>
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
          buttonText={'Yes, Remove User'}
        ></ConfirmDialog>
      )}
    </>
  );
};

export default ConfirmRemoveUser;
