import { useEffect, useState } from 'react';

import DataDisplay from '../../components/DataDisplay';
import { fetchDataUsage } from '../../services';

const Container = ({ id }: { id: string }) => {
  const [data, setData] = useState<{ title: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const response = await fetchDataUsage(id);
      setData(response);
      setLoading(false);
    }
    fetchData();
  }, []);

  return (
    <DataDisplay
      data={data}
      loading={loading}
      footerNote={<a href="/">Find out more about the metrics above</a>}
    />
  );
};

export default Container;
