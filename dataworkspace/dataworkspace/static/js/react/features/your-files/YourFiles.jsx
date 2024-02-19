import React, { useEffect, useRef, useState } from 'react';

import AWS from 'aws-sdk';

import AddFolderPopup from './components/AddFolderModal';
import BigDataMessage from './components/BigDataMessage';
import DeleteObjectsPopup from './components/DeleteObjectsModal';
import ErrorModal from './components/ErrorModal';
import FileList from './components/FileList';
import Header from './components/Header';
import TeamsPrefixMessage from './components/TeamsPrefixMessage';
import UploadFilesPopup from './components/UploadFilesModal';
import { getBreadcrumbs, getFolderName } from './utils';
import Credentials from './utils/Credentials';

import './styles/App.scss';

const popupTypes = {
  ADD_FOLDER: 'addFolder',
  UPLOAD_FILES: 'uploadFiles',
  DELETE_OBJECTS: 'deleteObjects',
};

const YourFiles = (props) => {
    const appConfig = props.config;
    const [s3, setS3] = useState(null);
    const [files, setFiles] = useState([]);
    const [folders, setFolders] = useState([]);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [filesToDelete, setFilesToDelete] = useState([]);
    const [foldersToDelete, setFoldersToDelete] = useState([]);
    const [currentPrefix, setCurrentPrefix] = useState(
        appConfig.initialPrefix.replace(/^\//, "").replace(/([^\/]$)/, "$1/")
    );
    const [bigDataFolder, setBigDataFolder] = useState(appConfig.bigdataPrefix);
    const [createTableUrl, setCreateTableUrl] = useState(appConfig.createTableUrl);
    const [isLoaded, setIsLoaded] = useState(false);
    const [error, setError] = useState(null);
    const [bucketName, setBucketName] = useState(appConfig.bucketName);
    const [region, setRegion] = useState(appConfig.region);
    const [showBigDataMessage, setShowBigDataMessage] = useState(false);
    const [popups, setPopups] = useState(
        Object.fromEntries(
            Object.entries(popupTypes).map((key, value) => [value, false])
        )
    );
    const [dragActive, setDragActive] = useState(false);
    const [prefix, setPrefix] = useState('');

    const fileInputRef = useRef(null);

    useEffect(() => {
        const awsConfig = {
            credentials: new Credentials(appConfig.credentialsUrl),
            region: appConfig.region,
            s3ForcePathStyle: true,
            ...(appConfig.endpointUrl ? { endpoint: appConfig.endpointUrl } : {}),
            httpOptions: {
              timeout: 10 * 60 * 60 * 1000
            }
        };

        console.log('AWS Config', awsConfig);
        setS3(new AWS.S3(awsConfig));
    });

    useEffect(() => {
        const handlePopState = (event) => {
            setCurrentPrefix(
                event.state && event.state.prefix
                    ? event.state.prefix
                    : props.config.initialPrefix
            );
            refresh();
        };

        window.addEventListener('popstate', handlePopState);

        return () => {
            window.removeEventListener('popstate', handlePopState);
        };
    }, []);

    const refresh = async (prefix) => {
        const rootPrefix = props.config.rootPrefix;
        const bigdataPrefix = props.config.bigdataPrefix;
        const showBigDataMessage = prefix === rootPrefix + bigdataPrefix;
        const params = {
            Bucket: bucketName,
            Prefix: prefix || currentPrefix,
            Delimeter: '/',
        };

        const listObjects = async () => {
            let response;
            try {
                response = await s3.listObjectsV2(params).promise();
            } catch (ex) {
                console.log('Error', ex);
                throw new Error(ex);
            }

            const files = response.Contents.filter(
                (file) => file.key !== params.Prefix
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
                    ? props.config.teamsPrefixes.map((team) => ({
                        Prefix: team.prefix,
                        isSharedFolder: true,
                        isSelected: false,
                    }))
                : [];
            
            const bigDataFolder =
                params.Prefix === rootPrefix
                    ? [
                        {
                            Prefix: rootPrefix + bigdataPrefix,
                            isBigData: true,
                            isSelected: false,  
                        },
                    ]
                : [];
            
            const foldersWithoutBigData = response.CommonPrefixes.filter((folder) => {
                return folder.Prefix !== `${rootPrefix}${bigdataPrefix}`;
            }).map((folder) => ({
                ...folder,
                isBigData: false,
                isSelected: false,
            }));
            const folders = teamsFolders
                .concat(bigDataFolder)
                .concat(foldersWithoutBigData);
            
            return {
                files,
                folders
            }
        };

        try {
            const data = await listObjects();
            setFiles(data.files);
            setFolders(data.folders);
            setCurrentPrefix(params.Prefix);
            setShowBigDataMessage(showBigDataMessage);
        } catch (ex) {
            showErrorPopup(ex)
        }
    };

    const onFileChange = (event) => {
        if (!event.target.files) {
            console.log('nothing selected');
            return;
        }

        const files = [];

        for (let i = 0; i < event.target.files.length; i++) {
            const file = event.target.files[i];
            file.relativePath = file.name;
            files.push(file);
        }

        setSelectedFiles(files);
        showPopup(popupTypes.UPLOAD_FILES);
        fileInputRef.current.value = null;
    };

    const navigateTo = async (newPrefix) => {
        window.history.pushState(
            { prefix: newPrefix },
            null,
            props.config.rootUrl + newPrefix
        );
        setPrefix(newPrefix);
        await refresh(newPrefix);
    }

    const onFileSelect = (file, isSelected) => {
        setFiles(prevFiles => {
            return prevFiles.map(f => {
                if (f.Key === file.Key) {
                    return { ...f, isSelected };
                }
                return f;
            });
        });
    }

    const onFolderSelect = (folder, isSelected) => {
        setFolders(prevFolders => {
            return prevFolders.map(f => {
                if (f.Prefix === folder.Prefix) {
                    return { ...f, isSelected };
                }
                return f;
            })
        })
    };

    const onBreadcrumbClick = async (e, breadcrumb) => {
        e.preventDefault();
        await navigateTo(breadcrumb.prefix)
    };

    const onRefreshClick = async () => {
        await navigateTo(currentPrefix);
    };

    const onUploadsComplete = async () => {
        await refresh(currentPrefix);
    };

    const onUploadClick = async (prefix) => {
        fileInputRef.current.click();
    };

    const onDeleteClick = async () => {
        const filesToDelete = files.filter((file) => file.isSelected);
        const foldersToDelete = folders.filter((folder) => folder.isSelected);

        console.log(
            `delete ${filesToDelete.length} files and ${foldersToDelete.length} folders`
        );

        setFilesToDelete(filesToDelete);
        setFoldersToDelete(foldersToDelete);

        showPopup(popupTypes.DELETE_OBJECTS);
    };

    const handleFileClick = async (key) => {
        const params = {
            Bucket: bucketName,
            Key: key,
            Expires: 15,
            ResponseContentDisposition: "attachment",
        };

        let url;
        try {
            url = await s3.getSignedUrlPromise('getObject', params);
            console.log(url);
            window.location.href = url;
        } catch (ex) {
            console.log('Error', ex);
            showErrorPopup(ex)
        }
    };

    const handleFolderClick = async (prefix) => {
        await navigateTo(prefix);
    };

    const handleDragEnter = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.currentTarget.contains(e.relatedTarget)) return;
        setDragActive(false);
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();    
    };

    const handleDrop = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        async function entries(directoryReader) {
            var entries = [];
            while (true) {
                var latestEntries = await new Promise((resolve, reject) => {
                    directoryReader.readEntries(resolve, reject);
                });
                if (latestEntries.length === 0) break;
                entries = entries.concat(latestEntries);
            }
            return entries;
        }

        async function file(fileEntry) {
            var file = await new Promise((resolve, reject) => {
                fileEntry.file(resolve, reject);
            });
            file.relativePath = fileEntry.fullPath.substring(1);
            return file;
        }

        async function getFiles(dataTransferItemList) {
            const files = [];
            const fileAndDirectoryEntryQueue = [];

            for (let i = 0; i < dataTransferItemList.length; ++i) {
                fileAndDirectoryEntryQueue.push(
                    dataTransferItemList[i].webkitGetAsEntry()
                );
            }

            while (fileAndDirectoryEntryQueue.length > 0) {
                const entry = fileAndDirectoryQueue.shift();
                if (entry.isFile) {
                    files.push(await file(entry));
                } else if (entry.isDirectory) {
                    fileAndDirectoryEntryQueue.push(
                        ...(await entries(entry.createReader()))
                    );
                }
            }
            return files;
        }

        setDragActive(false);
        setSelectedFiles(await getFiles(e.dataTransferItemList));
        showPopup(popupTypes.UPLOAD_FILES);
    };

    const showErrorPopup = (error) => {
        setError(error);
        setPopups(prevPopups => {
            const newState = { ...prevPopups };
            Object.keys(newState).forEach(key => newState[key] = false);
            return newState;
        });
    };

    const showNewFolderPopup = async (prefix) => {
        showPopup(popupTypes.ADD_FOLDER);
    };

    const showPopup = (popupName) => {
        setPopups(prevPopups => ({
            ...prevPopups,
            [popupName]: true
        }));
    };

    const hidePopup = (popupName) => {
        setPopups(prevPopups => ({
            ...prevPopups,
            [popupName]: false
        }));
    };

    const breadCrumbs = getBreadcrumbs(
        props.config.rootPrefix,
        props.config.teamsPrefix,
        currentPrefix
    );

    const currentFolderName = getFolderName(
        currentPrefix,
        props.config.rootPrefix
    );

    return (
        <div className="browser">
            <input 
                type="file"
                onChange={onFileChange}
                multiple={true}
                ref={fileInputRef}
                style={{ display: "none" }}
            />
            {error ? (
                <ErrorModal
                    error={error}
                    onClose={() => setError(null)}
                />
            ) : null}
            {popups.deleteObjects ? (
                <DeleteObjectsPopup 
                    s3={s3}
                    bucketName={props.config.bucketName}
                    filesToDelete={filesToDelete}
                    foldersToDelete={foldersToDelete}
                    onClose={async () => {
                        hidePopup(popupTypes.DELETE_OBJECTS);
                    }}
                    onSuccess={async () => {
                        await onRefreshClick();
                    }}
                />
            ) : null}
            {popups.addFolder ? (
                <AddFolderPopup 
                    s3={s3}
                    bucketName={props.config.bucketName}
                    currentPrefix={currentPrefix}
                    onSuccess={() => onRefreshClick()}
                    onClose={() => hidePopup(popupTypes.ADD_FOLDER)}
                    onError={(ex) => showErrorPopup(ex)}
                />
            ): null}
            {popups[popupTypes.UPLOAD_FILES] ? (
                <UploadFilesPopup 
                    s3={s3}
                    bucketName={props.config.bucketName}
                    currentPrefix={currentPrefix}
                    selectedFiles={selectedFiles}
                    folderName={currentFolderName}
                    onCancel={() => hidePopup(popupTypes.UPLOAD_FILES)}
                    onUploadsComplete={onUploadsComplete}
                />
            ) : null}

            <div
                className={`drop-zone ${dragActive ? "drag-active" : ""}`}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
            >
                <Header 
                    breadCrumbs={breadCrumbs}
                    canDelete={
                        folders.concat(files).filter((f) => f.isSelected).length > 0
                    }
                    currentPrefix={currentPrefix}
                    onBreadcrumbClick={onBreadcrumbClick}
                    onRefreshClick={onRefreshClick}
                    onNewFolderClick={showNewFolderPopup}
                    onUploadClick={onUploadClick}
                    onDeleteClick={onDeleteClick}
                />
                <FileList 
                    files={files}
                    folders={folders}
                    createTableUrl={createTableUrl}
                    onFolderClick={handleFolderClick}
                    onFolderSelect={onFolderSelect}
                    onFileClick={onFileClick}
                    onFileSelect={onFileSelect}
                />
                {showBigDataMessage ? (
                    <BigDataMessage 
                        bigDataFolder={bigDataFolder}
                        bucketName={bucketName}
                    />
                ) : null}
                {currentPrefix.startsWith('teams/') ? 
                    <TeamsPrefixMessage
                        team={props.config.teamsPrefixes.find(t => currentPrefix.startsWith(t.prefix))}
                        bucketName={bucketName}
                /> : null}
            </div>
        </div>
    );
};

export default YourFiles;