import React, { useEffect, useState } from 'react';

import { fetchDataUsage } from '../../services';
import { DataType } from '../../services';

type FetchDataContainerProps = {
  id: string;
  dataType: DataType;
  children: ({
    data,
    loading,
    error
  }: {
    data: { label: string; value: number }[];
    loading: boolean;
    error: string | null;
  }) => React.ReactNode;
};

const FetchDataContainer = ({
  id,
  dataType,
  children
}: FetchDataContainerProps) => {
  const [data, setData] = useState<{ label: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<null | string>(null);

  const childProps = {
    data,
    loading,
    error
  };

  useEffect(() => {
    async function fetchData() {
      const response = await fetchDataUsage(dataType, id);
      response instanceof Error
        ? setError(response.message)
        : setData(response);
      setLoading(false);
    }
    fetchData();
  }, []);

  return children(childProps);
};

export default FetchDataContainer;
