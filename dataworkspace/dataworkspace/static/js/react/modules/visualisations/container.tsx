import { useEffect, useState } from 'react';

import DataDisplay from '../../components/DataDisplay';
import { getVisualisationData } from '../../services';

const Container = () => {
  const [data, setData] = useState<{ title: string; value: string }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const response = await getVisualisationData();
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
      secondary
    />
  );
};

export default Container;
