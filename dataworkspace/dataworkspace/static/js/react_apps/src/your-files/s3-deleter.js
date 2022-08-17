export function S3Deleter(s3, bucket) {
  const bulkDeleteMaxFiles = 1000;
  let keys = [];

  async function deleteKeys() {
    let response;
    try {
      response = await s3
        .deleteObjects({ Bucket: bucket, Delete: { Objects: keys } })
        .promise();
    } catch (err) {
      console.error(err);
      throw err;
    } finally {
      keys = [];
    }
    return response;
  }

  async function scheduleDelete(key) {
    keys.push({ Key: key });
    if (keys.length >= bulkDeleteMaxFiles) return await deleteKeys();
  }

  async function flushDelete() {
    if (keys.length) return await deleteKeys();
  }

  console.log("here");
  return [scheduleDelete, flushDelete];
}
