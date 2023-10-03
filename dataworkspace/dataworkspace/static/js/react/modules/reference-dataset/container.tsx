import { useEffect, useState } from 'react';

import DataDisplay from '../../components/DataDisplay';
import { getRefData } from '../../services';

const Container = () => {
  const [data, setData] = useState<{ title: string; value: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const response = await getRefData();
      setData(response);
      setLoading(false);
    }
    fetchData();
  }, []);

  return (
    <DataDisplay
      data={data}
      loading={loading}
      error="There seems to be an issue"
      footerNote={<a href="/">Find out more about the metrics above</a>}
    />
  );
};

export default Container;
