import React, { useEffect, useRef, useState } from 'react';

import LoadingBox from '@govuk-react/loading-box';
import AWS from 'aws-sdk';

import AddFolderPopup from './components/AddFolderPopup';
import BigDataMessage from './components/BigDataMessage';
import DeleteObjectsPopup from './components/DeleteObjectsPopup';
import ErrorPopup from './components/ErrorPopup';
import FetchData from './components/FetchData';
import FileList from './components/FileList';
import Header from './components/Header';
import PopupTypes from './components/PopupTypes';
import TeamsPrefixMessage from './components/TeamsPrefixMessage';
import UploadFilesPopup from './components/UploadFilesPopup';
import { getBreadcrumbs, getFolderName } from './utils';
import Credentials from './utils/Credentials';

import './styles/App.scss';

const YourFiles = ({ config }) => {
    const bucketName = config.bucketName;
    const teamsPrefix = config.teamsPrefix;
    const rootPrefix = config.rootPrefix;
    const bigdataPrefix = config.bigdataPrefix;
    const teamsPrefixes = config.teamsPrefixes;

    const awsConfig = {
        credentials: new Credentials(config.credentialsUrl),
        region: config.region,
        s3ForcePathStyle: true,
        ...(config.endpointUrl ? { endpoint: config.endpointUrl } : {}),
        httpOptions: {
          timeout: 10 * 60 * 60 * 1000
        }
    };
    const s3 = new AWS.S3(awsConfig);

    const [currentPrefix, setCurrentPrefix] = useState(
        config.initialPrefix.replace(/^\//, '').replace(/([^\/]$)/, '$1/')
    );
    const [files, setFiles] = useState([]);
    const [folders, setFolders] = useState([]);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [filesToDelete, setFilesToDelete] = useState([]);
    const [foldersToDelete, setFoldersToDelete] = useState([]);
    const [error, setError] = useState(null);
    const [showBigDataMessage, setShowBigDataMessage] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const [popups, setPopups] = useState({});
    const [loading, setLoading] = useState(true);

    const fileInputRef = useRef(null);

    useEffect(() => {
        const handlePopState = (event) => {
            setCurrentPrefix(
                event.state && event.state.prefix
                ? event.state.prefix
                : config.initialPrefix
            );
        };

        console.log('AWS Config', awsConfig);

        refresh();

        window.addEventListener('popstate', handlePopState);
    }, []);

    const refresh = async (prefix) => {
        const rootPrefix = config.rootPrefix;
        const showBigDataMessage = prefix === rootPrefix + bigdataPrefix;
        const params = {
            Bucket: bucketName,
            Prefix: prefix || currentPrefix,
            Delimiter: '/'
        };

        try {
            setLoading(true);
            const data = await FetchData(rootPrefix, bigdataPrefix, teamsPrefixes, params, awsConfig);

            setFiles(data.files);
            setFolders(data.folders);

            setCurrentPrefix(params.Prefix);
            setShowBigDataMessage(showBigDataMessage);

            console.log('files:', files);
            console.log('folders:', folders);

            setLoading(false);
        } catch (ex) {
            console.log('Error', ex);
            showErrorPopup(ex);
        }
    };

    const navigateTo = async (prefix) => {
        window.history.pushState(
            { prefix: prefix },
            null,
            config.rootUrl + prefix
            );
            setCurrentPrefix(prefix);
            await refresh(prefix);
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
            showPopup(PopupTypes.UPLOAD_FILES);
            fileInputRef.current.value = null;
    };

    const onFileSelect = (file, isSelected) => {
        setFiles(prevFiles => {
            return prevFiles.map(f => {
                if (f.Key === file.Key) {
                    return { ...f, isSelected };
                }
                return f;
            });
        });
    };

    const onFolderSelect = (folder, isSelected) => {
        setFolders(prevFolders => {
            return prevFolders.map(f => {
                if (f.Prefix === folder.Prefix) {
                    return { ...f, isSelected };
                }
                return f;
            });
        });
    };

    const onBreadcrumbClick = async (e, breadcrumb) => {
        e.preventDefault();
        await navigateTo(breadcrumb.prefix);
    };

    const onRefreshClick = async () => {
        await navigateTo(currentPrefix);
    };

    const onUploadsComplete = async () => {
        await refresh(currentPrefix);
    };

    const onUploadClick = async () => {
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

        showPopup(PopupTypes.DELETE_OBJECTS);
    };

    const handleFileClick = async (key) => {
        const params = {
            Bucket: bucketName,
            Key: key,
            Expires: 15,
            ResponseContentDisposition: 'attachment',
        };

        let url;
        try {
            url = await s3.getSignedUrlPromise('getObject', params);
            console.log(url);
            window.location.href = url;
        } catch (ex) {
            console.log('Error', ex);
            showErrorPopup(ex);
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
                const entry = fileAndDirectoryEntryQueue.shift();
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
        showPopup(PopupTypes.UPLOAD_FILES);
    };

    const showNewFolderPopup = async () => {
        showPopup(PopupTypes.ADD_FOLDER);
    };

    const showErrorPopup = (error) => {
        setError(error);
        setPopups(prevPopups => {
            const newState = { ...prevPopups };
            Object.keys(newState).forEach(key => newState[key] = false);
            return newState;
        });
    };

    const showPopup = (popupName) => {
        setPopups(prevPopups => ({
          ...prevPopups,
          [popupName]: true,
        }));
    };
    
    const hidePopup = (popupName) => {
        setPopups(prevPopups => ({
            ...prevPopups,
            [popupName]: false,
        }));
    };

    const breadCrumbs = getBreadcrumbs(
        rootPrefix,
        teamsPrefix,
        currentPrefix
    );

    const currentFolderName = getFolderName(
        currentPrefix,
        rootPrefix
    );
    
    return (
        <div className="browser">
            <input 
                type="file"
                onChange={onFileChange}
                multiple={true}
                ref={fileInputRef}
                style={{ display: 'none' }}
            />
            {error ? (
                <ErrorPopup
                    open={!!error}
                    error={error}
                    onClose={() => setError(null)}
                />
            ) : null}
            {popups.deleteObjects ? (
                <DeleteObjectsPopup 
                    open={popups.deleteObjects}
                    s3={s3}
                    bucketName={bucketName}
                    filesToDelete={filesToDelete}
                    foldersToDelete={foldersToDelete}
                    onClose={async () => {
                        hidePopup(PopupTypes.DELETE_OBJECTS);
                    }}
                    onSuccess={async () => {
                        await onRefreshClick();
                    }}
                />
            ) : null}
            {popups.addFolder ? (
                <AddFolderPopup 
                    open={popups.addFolder}
                    s3={s3}
                    bucketName={bucketName}
                    currentPrefix={currentPrefix}
                    onSuccess={() => onRefreshClick()}
                    onClose={() => hidePopup(PopupTypes.ADD_FOLDER)}
                    onError={(ex) => showErrorPopup(ex)}
                />
            ) : null}
            {popups.uploadFiles ? (
                <UploadFilesPopup 
                    open={popups.uploadFiles}
                    s3={s3}
                    bucketName={bucketName}
                    currentPrefix={currentPrefix}
                    selectedFiles={selectedFiles}
                    folderName={currentFolderName}
                    onCancel={() => hidePopup(PopupTypes.UPLOAD_FILES)}
                    onUploadsComplete={onUploadsComplete}
                />
            ) : null}
            <LoadingBox loading={loading}>
                <div
                    className={`drop-zone ${dragActive ? 'drag-active' : ''}`}
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
                        createTableUrl={config.createTableUrl}
                        onFolderClick={handleFolderClick}
                        onFolderSelect={onFolderSelect}
                        onFileClick={handleFileClick}
                        onFileSelect={onFileSelect}
                    />
                    
                    {showBigDataMessage ? (
                        <BigDataMessage 
                            bigDataFolder={bigdataPrefix}
                            bucketName={bucketName}
                        />
                    ) : null}
                    {currentPrefix.startsWith('teams/') ? 
                        <TeamsPrefixMessage
                            team={teamsPrefixes.find(t => currentPrefix.startsWith(t.prefix))}
                            bucketName={bucketName}
                    /> : null}
                </div>
            </LoadingBox>
        </div>
    );
};

export default YourFiles;