---
title: Releases
---

## Tag your release

1. View the current [tags in Data Workspace](https://github.com/uktrade/data-workspace/tags)

- Make a note of the latest tag
- Check out the master branch and pull the latest.
- Create a new tag from the master branch following this format `v<year>-<month>-<day>` eg. v2024-01-19
- Push the new tag to Github

**Example of how to tag and push**

```
git tag -a v2024-01-19 -m v2024-01-19
```

```
git push origin v2024-01-19
```

## Create draft release notes

1. View the current [tags in Data Workspace](https://github.com/uktrade/data-workspace/tags)

- Click on the tag that you just created/pushed
- [Compare your tag with the previous](https://github.com/uktrade/data-workspace/compare). This will give you a list of all the changes to be released
- View the current [releases in Data Workspace](https://github.com/uktrade/data-workspace/releases)
- Click "Draft a new release"
- Click the "[Generate release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes)" option
- Check that the form is in the format below
- Check the option "Set as latest release"
- Click "Save as draft"

**Example of release notes**

```
## What's Changed

The main change today was a fix to an issue where external links in Quicksight dashboards weren't working. They were opening a new tab, but that tab remained blank. Now, that new tab loads the external page as it should.

* build: add latest QuickSight embedding SDK (but don't use it) by @michalc in https://github.com/uktrade/data-workspace/pull/2949
* fix: remove reference to source map to get collectstatic to work by @michalc in https://github.com/uktrade/data-workspace/pull/2950
* feat: use latest Quicksight embedding SDK by @michalc in https://github.com/uktrade/data-workspace/pull/2951
* feat: set COOP to same-origin-allow-popups for Quicksight by @michalc in https://github.com/uktrade/data-workspace/pull/2952

**Full Changelog**: https://github.com/uktrade/data-workspace/commits/v2024-01-15
```

##Release tag to production

1. Visit the build job in Jenkins

- Click "build with parameters" and wait until you have the option to click "proceed to staging"
- Click "proceed"
- Check the changes in [staging](https://data.trade.staging.uktrade.digital/)
- Click "proceed" to production
- Check the changes in [production](https://data.trade.gov.uk/)
- Go back to the [releases in Github](https://github.com/uktrade/data-workspace/releases)
- Click on the draft release you created earlier
- Click "Publish release"

##Post in the DW channel

Once the release is complete you can then notify everyone in the Data Workspace Teams channel. Use the format below.

```
Data Workspace <tag> has just been released

Whats changed?
<high level description of what has been released>

For more details please see the release notes
```
