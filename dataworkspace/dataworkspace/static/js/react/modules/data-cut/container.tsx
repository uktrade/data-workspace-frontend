import { useEffect, useState } from 'react';

import DataDisplay from '../../components/DataDisplay';
import { getDataCut } from '../../services';

const Container = () => {
  const [data, setData] = useState<{ title: string; value: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const response = await getDataCut();
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
