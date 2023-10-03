import { useEffect, useState } from 'react';

import DataDisplay from '../../components/DataDisplay';
import { getSourceData } from '../../services';

const Container = () => {
  const [data, setData] = useState<{ title: string; value: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const response = await getSourceData();
      setData(response);
      setLoading(false);
    }
    fetchData();
  }, []);

  return <DataDisplay data={data} loading={loading} />;
};

export default Container;
