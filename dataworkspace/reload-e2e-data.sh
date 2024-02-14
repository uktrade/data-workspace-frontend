#!/bin/sh

django-admin flush --noinput
echo "Cleared existing django data from DB"
django-admin loaddata --ignorenonexistent --verbosity=3 dataworkspace/e2e_fixtures.json
echo "Loaded fixtures data"
