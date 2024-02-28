import AWS from 'aws-sdk';

const FetchData = async (rootPrefix, bigdataPrefix, teamsPrefixes, params, awsConfig) => {
    const s3 = new AWS.S3(awsConfig);
    let response;

    try {
        response = await s3.listObjectsV2(params).promise();
    } catch (ex) {
        console.log('Failed to fetch objects from S3:', ex);
        throw new Error(ex);
    }

    const files = response.Contents.filter(
        (file) => file.Key !== params.Prefix
    ).map((file) => ({
        ...file,
        formattedDate: new Date(file.LastModified),
        isSelected: false,
    }));

    files.sort(function(a, b) {
        return b.formattedDate - a.formattedDate;
    });

    const teamsFolders =
    params.Prefix === rootPrefix
        ? teamsPrefixes.map((team) => ({
            Prefix: team.prefix,
            isSharedFolder: true,
            isSelected: false
        }))
    : [];

    const bigDataFolder =
        params.Prefix === rootPrefix
        ? [
            {
                Prefix: rootPrefix + bigdataPrefix,
                isBigData: true,
                isSelected: false
            },
        ]
    : [];

    const foldersWithoutBigData = response.CommonPrefixes.filter((folder) => {
        return folder.Prefix !== `${rootPrefix}${bigdataPrefix}`;
    }).map((folder) => ({
        ...folder,
        isBigData: false,
        isSelected: false
    }));

    const folders = teamsFolders
        .concat(bigDataFolder)
        .concat(foldersWithoutBigData);
    
    return {
        files,
        folders
    };
};

export default FetchData;