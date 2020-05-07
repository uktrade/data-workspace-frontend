# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## 2020-05-07

### Changed

- Multiuser Supserset to use CSP
- Fix redirects returned by Superset to maintain HTTPS
- Put Superset behind the VPN
- Made s3sync Fargate 1.4.0 compatible

## 2020-05-06

### Changed

- Fix issue where proxy was denying access to accounts api endpoint
- Version of Fargate on Docker pull-through cache to allow for more space
- Avoid creating a new task definition if cpu/memory are specified

### Added

- Multiuser instance of Superset behind the proxy for testing

## 2020-05-05

### Changed

- Attempt to address git repo corruption by uploading all files in .git as soon as they are created

## 2020-05-04

### Changed

- Fix Theia missing menu on new builds by locking dependencies
- Default to Python 3 in Theia
- Fewer errors when running apt-get update in Theia
- Allow popups in wrapped visualisations

## 2020-05-01

### Changed

- Serialize models to python before logging to event log 

## 2020-04-30

### Changed

- The command in the sample environment for local development to make working on the spawning system a bit easier

### Added

- The ability to optionally wrap a visualisation in an iframe, towards adding a header

## 2020-04-29

### Added

- Data explorer as a hidden tool
- Pass the name of the schema an app can write to via an environment variable
- Allow workers to be made from blobs, for Superset maps

## 2020-04-28

### Changed

- Automatically lowercase emails in data vis UI catalogue page before searching db.
- Don't show in the visualisation UI or give visualisation/tools access to deleted datasets
- Log the URL on the same line as the authenticated user is logged

## 2020-04-27

### Added

- User access type checkbox to data vis UI catalogue page.

## 2020-04-26

### Changed

- Slightly better handling of concurrent giving of visualisation access

## 2020-04-25

### Changed

- Return database connections to the pool at the start of streaming responses that don't use them, as an attempt to address database connection usage

## 2020-04-24

### Added

- A zero-width space after an underscore in the visualisation datasets page to encourage line breaks in more readable places
- Eligibility criteria to visualisation catalogue items.
- Eligibility criteria to data vis UI catalogue page.
- Create a Zendesk ticket when a user requests access to a visualisation
- Send an email notification to visualisation contacts on access request
- Pre-fill user email when giving access by following an email link
- Send an email to the user when their access request has been granted

### Changed

- Close database connection after each Celery task as attempt to address database connection usage/(leak?)
- Smaller chance of parallel starts of the same application surfacing an error
- Updated the text on the data vis ui approvals page to be more explicit around the requirements.
- Publishing page for data vis UI.

## 2020-04-23

### Added

- Ability to unapprove visualisations.
- Automatic granting of permission for data vis creators to manage unpublished visualisations, which will let them view the catalogue page before publication.

### Changed

- Client-side validation of `short_description` for visualisation catalogue items no longer occurs.
- The ability to see what Datasets a visualisation has access to

## 2020-04-22

### Changed

- Bumped GitLab to latest 12.6
- Bumped Git and OpenSSL to latest on Alpine 3.10
- Bumped GitLab to latest 12.7
- Wrap each of dataset schema and table in double quotes
- RPostgres to the RStudio base image

## 2020-04-21

### Added

- Apache Superset as a hidden tool for testing
- Model for application templtae approvals (specifically for visualisations).

### Changed

- Better logging from the proxy that should make it easier to calculate stats on visualisation access

## 2020-04-20

### Changed

- Remove of string normalisation from pre-commit config
- Sort visualisations by name

## 2020-04-18

### Changed

- More locking to avoid "tuple concurrently updated" errors when GRANTing database privileges
- Use GitLab developer permissions for a visualisation preview, rather than the same permissions as viewing the production visualisation

### Added

- Caching of GitLab developer permissions

## 2020-04-17

### Added

- Page in the "Data Visualisation UI" for editing its entry in the catalogue.

### Changed

- Fixed api url typo in proxy
- More accurate database user name for visualisations to make debugging easier
- Attempt to avoid "tuple concurrently updated" errors by wrapping GRANT CONNECT with a lock

### Added

- Optional reference code added to the dataset model.
- Reference number added to dataset source models.
- Downloads through data workspace are now prepended with the reference code and reference number above if set.

## 2020-04-16

### Added

- Database credentials to the environment in R Studio, so Shiny apps can be developed that would also access their database credentials from the environment
- Migration for manage_unpublished_visualisations
- The automatic creation of ApplicationTemplate and VisualisationCatalogueItem from a GitLab project

### Changed

- Allow the GitLab pipeline to take 30 minutes before cancelling it
- Use the RStudio CMD from the Dockerfile to make local development on the container more like production by default
- Success alert more similar to error alert

## 2020-04-15

### Changed

- Version of git to the one that is now available in Alpine
- Stopped the setting of host_pattern: it's already not used
- Squashed migrations to later support removal of `host_pattern`
- Remove unused `host_pattern`
- Reduce usage of application "name" so there is less to setup per visualisation
- Search GitLab for visualisations using topic rather than group, to remove admin involvement

### Added

- Common spawner options from the environment to avoid copy+pasting options when creating visualisations

## 2020-04-14

### Changed

- `host_exact` column for application templates to `host_basename`.

## 2020-04-14

### Added

- Theia IDE as a hidden tool for testing
- A message on the conditions that need to be met before sharing a visualisation
- The ablity to remove visualisation view access
- Catalogue detail page for visualisations

## 2020-04-09

### Added

- New API endpoint listing historic application instances at `/api/v1/application-instance/instances`

### Changes
- Log access requests and permission changes to the event log

## 2020-04-08

### Added

- The ability for a user to share a visualisation with another user
- The ability to give permissions to a visualisation via an email with uppercase letters

### Changed

- Only showing visualisations on the Visualisations page that can be developed by the current user, and that are already linked with a Visualisations model

- Enforce the requirement that the user must have GitLab developer access to a project to be able to manage it

## 2020-04-07

### Changed

- Updated text on "user unauthorised to use tools" page to remove the requirement for them to have SC.
- Fewer exceptions polling Fargate for task stopped time
- Fewer exceptions when removing database users: specifically when users had privileges on schemas without tables
- Fewer exceptions when trying to find the CPU of a task

### Added

- Initial version of button to release a visualisation to production

## 2020-04-06

### Added

- The commit ID of the production visualisation

## 2020-04-03

### Added

- Instrumentation for Elastic APM

### Changed

- Moved the "no permissions" warning on the datacut page into the top section.

## 2020-04-02

## Added

- A tools page for users who don't have access to tools, telling them what it is and how to get access.

## 2020-04-01

### Changed

- Some of the fixed-length sleeps in the integration tests to polling the healthcheck endpoint until it returns non-error response.
- Styles in the visualisation page to better display long branch names
- A production section in the master branch of a visualisation page

### Added

- A slightly magic /__mirror/ path accessible on the domain of each application that routes to our S3 mirror. Specifically for applications that need map tiles.
- New API endpoint for listing user accounts for consumption by data flow

## 2020-03-30

### Added

- New API endpoint listing eventlog entries at `/api/v1/eventlog/events`

### Changed

- The timeout for a visualisation build to complete to 30 minutes

## 2020-03-27

### Changed

- Added support for `double precision` columns to Google Data Studio integration

### Added

- Visualisation admin page to view users with access

## 2020-03-26

### Changed

- Allow Google Data Studio to fetch from unpublished datasets [they each still have to be individually enabled for Google Data Studio access]
- Upgrade JupyterLab images to v2.0.0.
- Fix the custom JupyterLab database-connector plugin to work in v2.0.0.

## 2020-03-24

### Changed

- Fix the "Skip to main content" link: it would always link to the home page
- Update the number of rows shown in the preview panel on a reference dataset to 1000
- Refactor to add intermediate template in chain to support the visualisations side navigation not being inside the `main` html element
- Rename template block from inner_content to content
- Move visualisations side navigation outside of the `main` html element

## 2020-03-23

- Fix Google Data Studio link

## 2020-03-22

### Changed

- Update the architecture to include GitLab

## 2020-03-21

### Changed

- Page per visualisation

## 2020-03-20

### Changed

- Version of packages in RStudio image to latest in current Debian mirror
- Correct mirrors branch to master
- Fix Debian mirror missing certain files
- Bump Lowhaio in mirror jobs to avoid error when re-using connections that have closed

## 2020-03-19

### Changed

- Fix the link to GitLab shown on the visualisations page if the user has not yet visited GitLab
- Ensure to get RStudio packages from our mirror, not the main Debian repo, to see if this fixes packages not installing

## 2020-03-18

### Added

- Code snippets to master datasets for users who have access to tools, for getting quickly started working with the data.
- 'Support and feedback' link to header/footer.

### Changed

- Text on the 'feedback' page to 'Support and feedback' and updated help text.

### Changed

- Fixed links to branches and commits in visualisations page
- GitLab load balancer to be in own subnet with NACL
- Communication from the admin application and GitLab via port 80 on private IP

## 2020-03-17

### Changed

- Use VPC endpoint for ECR API access (needed for upcoming changes to access the API from the GitLab runner, which does not have internet access)
- When determining the spawner status, take GitLab pipeline status and time into account, otherwise the spawner is marked as stopped because it takes too long for the task to be created
- Fix a bug with "you have access" filter resulting in wrong datasets being included and/or duplicated.


## 2020-03-14

### Added

- Trigger of a GitLab build for visualisations


## 2020-03-13

### Added

- A check to see if a tag already exists in ECR


## 2020-03-12

### Changed

- The lifecycle policy on the GitLab EBS volume to prevent accidental destruction

### Added

- A GitLab runner to run visualisation builds


## 2020-03-09

### Added

- "Help" link to header/footer
- A dataset filter for uses to only see datasets they have access to

### Changed

- Master/Datacut dataset descriptions changed to rich text fields

### Removed

- Published/Updated dates from dataset detail views

### Added

- Links to preview visualisations in the visualisations page (but nothing in place to build these if the tags don't exist)
- The commit ID when starting an app via a specific commit ID


## 2020-03-07

### Changed

- Fixed applications not auto shutting down


## 2020-03-06

### Added

- A "warning" section for data links that point at externally-hosted sources.
- The texlive package to RStudio to enable creation of PDFs

### Changed

- Remove now-unnecessary constraint on host_exact,host_pattern
- Require host_exact to be populated for tools on start


## 2020-03-05

### Changed

- Remove unused "User Provided" application
- Clickable links in reference dataset description
- Support more double-hyphens in hosts
- De-generalise how hosts are converted to Docker tags for visualisations
- De-generalise how hosts are converted to correct ApplicationTemplates for tools


## 2020-03-04

### Changed

- Fix incorrection change of name -> nice name in Django admin
- Move the `contact` section to the bottom of the dataset detail view.

### Added

- Tools section in Admin


## 2020-03-03

### Added

- New permissions to allow users to manage only unpublished datasets.
- A new group, "Subject Matter Experts", that has permissions to manage unpublished master and datacut datasets.

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


## 2020-02-26

### Added

- Mirror of NLTK


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
