#!/bin/sh

django-admin collectstatic --noinput
$@
