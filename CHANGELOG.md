# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


## 2019-12-16

### Changed

- Fix bug where admins were unable to create master datasets with "authentication only" permissions


## 2019-12-16

### Changed

- Fix bug on user admin form where long dataset names were not visible
- Fix bug with new users seeing an error on loading any page: relating to SSO integration


## 2019-12-12

### Added

- New model `SourceTag`
- New `source_tag` field added to `MasterDataset` and `DataCutDataset` pointing to `SourceTag`


## 2019-12-12

### Added

- New changelog `CHANGELOG.md`.
- New frequency field on `SourceTable` and `SourceView` models.

### Changed
- Split `DataSets` out into `MasterDataset` and `DataCutDataset` in the admin.
- Split `DataSetUserPermission` out into `MasterDatasetUserPermssion` and `DataCutDatasetUserPermission` in the admin.
- New filterable dataset user permission selector on the user admin page.
- Split `dataset.html` out into `data_cut_dataset.html` and `master_dataset.html`.
- Removes unused dataset fields `redactions` and `volume`.
