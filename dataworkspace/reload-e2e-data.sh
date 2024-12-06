#!/bin/sh

django-admin flush --noinput
echo "Cleared existing django data from DB"
django-admin waffle_flag HOME_PAGE_FLAG --everyone --create
django-admin waffle_flag ACCESSIBLE_AUTOCOMPLETE_FLAG --everyone --create
django-admin waffle_flag SUGGESTED_SEARCHES_FLAG --everyone --create
django-admin waffle_flag ALLOW_REQUEST_ACCESS_TO_DATA_FLOW --everyone --create
echo "Feature flags have been set"
django-admin loaddata --ignorenonexistent --verbosity=3 dataworkspace/e2e_fixtures.json
echo "Loaded fixtures data"
