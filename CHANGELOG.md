# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


## 2020-03-04

### Changed

- Fix incorrection change of name -> nice name in Django admin
- Remove unused (and not-planned-to-be-used) 'user-provided' code and config.


## 2020-03-03

### Changed

- Reduce usage of application 'name' in favour of nice_name and id
- Upgrade to Django 3.0.3


## 2020-02-28

### Added

- If the current user has developer or higher privileges on each GitLab project. This is mostly to find out how slow the API requests are going to be in production.


## 2020-02-26

### Changed

- Remove the permissions check for showing the Visualisations tab to try to reduce the effect of running out database connections.
- The location of the Menu button in the main navigation on mobile to make up for the lack of the GOV UK logo + crown which the GDS styles assume.


### Added

- Support for Google Tag Manager to manage analytics
- FontAwesome attribution in the source of the Files page
- Branches in the Visualisations page


## 2020-02-25

### Changed

- Fixed the broken link to GitLab from the visualisations page
- Removed duplicated word in visualisations page


## 2020-02-25

### Changed

- The visualisations page shows a message asking the user to visit GitLab if they haven't already.
- The visualisations page asks the user to contact support if they have no access to any projects.
- The visualisations page shows all internal visualisations if the user hasn't yet visited GitLab, or all the visualisations visible projects if they have.
- Where the ipython directory is, from the home directory that is synced using mobius3, to /tmp. This avoids occasional sqllite "attempt to write a readonly database" errors.


## 2020-02-24

### Changed

- Sync all hidden files to and from S3, specifically for .gitignore
- The proxy to support Websocket sub-protocols
- The version of tidyverse in the RStudio image to support pivot_longer

### Added

- A remote desktop tool, hidden for now so it does not show in the UI
- A visualisations page, just showing links to projects in a certain group in GitLab, accessible to superusers and users that have the can_develop_visualisations permission.


## 2020-02-20

### Changed

- Separated the JupyterLab Python and R config directories to avoid strange behavior/conflicts when we come to sync them to S3
- Separated the JupyterLab Python and R data and runtime directories to avoid strange behavior/conflicts when we come to sync them to S3
- Default shell in JupyterLab to bash


## 2020-02-17

### Changed

- Updated the reference data set view to limit the number of rows previewed.


## 2020-02-19

### Added

- Packages in RStudio to include more frequently-used ones


## 2020-02-17

### Changed

- Link in README when developing locally
- For each tool at mytool-[sso-id].domain.com, allow mytool-[sso-id]--9000.domain.com to route through to the application.


## 2020-02-14

### Added

- Dataset user permissions can be viewed / modified from the dataset admin page

### Changed

- The CSP header to explicitly allow Websocket requests by named domain: required for Safari since 'self' does not seem to work
- Remove source created date from data cut and master dataset detail pages.


## 2020-02-12

## Added

- A loading spinner on the 'tool spawning' page.


## 2020-02-11

### Changed

- Set expectations for users requesting access to datasets.
- Fixed passing environment variables to visualisations with database credentials.


## 2020-02-10

### Changed

- Local development domain set to `dataworkspace.test`
- Increase streaming download queue timeout to 2 minutes
- Rephrased and merged request access form goal and justification questions into one
- Deleting datasets via the admin now sets the `deleted` flag
- Admin users can view unpublished datasets via the catalogue
- Admin users can access unpublished source tables via tools


## 2020-02-06

### Changed

- Which debian repository is used in JupyterLab R and Python, to our mirror, so packages can be installed from inside them

### Added

- Retries when fetching dependencies when building the RStudio image. The S3 mirror is surprisingly flaky.


## 2020-02-05

### Changed

- JupyterLab R and JupyterLab Python docker images have been cleaned up.
- Add the ability to sudo as the jovyan user.
- Trigger when a user creates tables in their own schema using CREATE TABLE AS, so they are accessible in other tools
- Request access, eligibility criteria and view/link/query/reference data download URLs are now prefixed by the dataset
  URL (e.g. `/datasets/<UUID>/request-access`).
- Dataset group references are removed from user-facing pages.
- Data group editing is removed from the admin interface.

### Added

- Add admin pages for SourceView and SourceTable


## 2020-02-04

### Added

- Content-Security-Policy header to mitigate risk of egress

### Changed

- JupyterLab R and JupyterLab Python docker images have been migrated to Debian 10.


## 2020-02-03

### Added

- Referrer-Policy header to avoid sending the Referer header in any case


## 2020-02-03

### Changed

- The amount of memory and CPU available to visualisations


## 2020-01-31

### Changed

- Search page is enabled for everyone
- Dataset group pages now redirect to search results
- Home page now displays the new search page with links in header and footer

### Removed

- Old home page
- Dataset group pages
- datasets-search feature flag


## 2020-01-30

### Changed

- Up queue timeout on streaming downloads to try to mitigate "queue full" errors


## 2020-01-28

### Changed

- Version of mobius3 to sync the mode of files in tools


## 2020-01-28

### Added

- New header layout for the search UI (only visible with users with a feature flag set)
- Navigation links in the footer (behind a feature flag)
- New about page


## 2020-01-27

### Changed

- Version of mobius3, and its configuration to fix syncing issues with .git directories

### Added

- Adds an admin page for `CustomDatasetQuery` models.
- 2 new fields were added to the `DataSet` and `ReferenceDataset` models:
    - `information_asset_manager`
    - `information_asset_owner`


## 2020-01-22

### Changed

- What directories are synced from tools to include .ssh, to better support the upcoming GitLab integration.


## 2020-01-20

### Changed

- Bumped version of nginx to 1.16.1-r2
- Use dns-rewrite-proxy instead of dnsmasq to allow gitlab.publicdomain.com to resolve to a private ip address inside tools
- Security groups to allow the tools to communicate with gitlab on port 22

### Added

- SSH to each tool, so git can connect using SSH.


## 2020-01-16

### Changed

- Fix issue where admins were unable to create new users
- Update search results on filter / search input change
- Add search input "placeholder" label


## 2020-01-15

### Changed

- Redis and RDS security groups: they do not need explicit access to Cloudwatch


## 2020-01-14

### Added

- git to RStudio and JupyterLab, ready for the upcoming connection to GitLab


### Changed

- Version of mobius3, to include changes to better sync nested directories, for the upcoming connection to GitLab from tools
- Which local files are synced to S3 from the tools local home folder to include `.git`
- Gitlab, running in Docker, but on its own EC2 instance


## 2020-01-08

### Added

- Initial version of the datasets search page with data use and source filters. Only available to Data Workspace staff users at the moment.

# 2020-01-10

### Changed

- Display data protection messaging on tool loading pages


## 2020-01-09

### Changed

- Error pages to be more in keeping with GDS recommendations, and to encourage users to log into ZScaler


## 2020-01-08

### Added

- The data.table package in the RStudio docker image


## 2020-01-07

### Added

- Allow for filtering by source tag on dataset admin listing pages


## 2020-01-06

### Added

- Give users permissions to access reference dataset tables via tools
- Give visualisations permissions to access reference data

### Changed

- Fix bug where reference dataset field could not be deleted if it was set to sort field
- Fix bug where errors were not displayed if record deletion failed
- Fix issue where deleting a record failed if the record linked to an "external" reference dataset
- Fix bug where incorrect name was returned if display name was of type 'linked reference dataset'


## 2019-12-27

### Added

- Missing migration on ReferenceDataset and ReferenceDatasetField
- DataSet access to visualisation applications

### Changed

- Bumped version of OpenSSL to 1.1.1d-r2


## 2019-12-23

### Changed

- Tables created in pgAdmin now have the correct owner: the permanent role of the current user. This means they won't prevent the database user from being cleaned up, and means they will be accessible from other tools.


## 2019-12-20

### Added

- Adds django-waffle for feature flag support
- New field `uuid` added to `ReferenceDataset` and populated.
- New field `source_tags` added to `ReferenceDataset`.
- New shared url and view for datasets and reference datasets with format `/datasets/<uuid>#slug`

### Changed

- Old dataset and reference dataset endpoints (`/<group slug>/<dataset slug>/`) now redirect to the new url style above
- Update all templates to use `get_absolute_url()` for datasets and reference datasets

## 2019-12-18

### Added

- Display a list of data fields on the dataset page

### Changed

- Remove ability to upload files as part of a support request.


## 2019-12-17

### Added

- Cronjob to delete unused datasets database users to work around a de facto maximum number of users in a Postgres database.


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
