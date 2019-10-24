#!/bin/bash
: <<'help'
ARGS: - 1: Directory of project repo: i.e. /Users/django/data-workspace
Script that automates environment setup for local Mac machine. Can be run multiple times.
- Install postgres
- Start postgres
- Create dataworkspace db
- Install redis
- Start redis server
- Install virtualenv and virtualenvwrapper
- Set configuration for virtualenv and virtualenvwrapper
- Create virtualenv dataworkspace
- Modify post_activate hook to source our env variables
- Install project python requirements

After script completion please activate the environment and follow normal process for running 
Django project.
i.e.
- workon dataworkspace
- cd dataworkspace/dataworkspace
- python manage.py migrate
- python manage.py runserver
help

if [ -z "$1" ]
then
      echo "Directory of project repo is required as an argument \$1"
      exit
fi

brew install postgres
pg_ctl -D /usr/local/var/postgres start
createdb dataworkspace
brew install redis
brew services start redis
pip install virtualenv
pip install virtualenvwrapper

# needed for virtualenvwrapper
grep -qF "WORKON_HOME" ~/.bash_profile || echo "export WORKON_HOME=~/.virtualenvs" >> ~/.bash_profile
grep -qxF "export VIRTUALENVWRAPPER_PYTHON=/usr/local/bin/python3" ~/.bash_profile || echo "export VIRTUALENVWRAPPER_PYTHON=/usr/local/bin/python3" >> ~/.bash_profile
grep -qxF "export VIRTUALENVWRAPPER_VIRTUALENV=/usr/local/bin/virtualenv" ~/.bash_profile || echo "export VIRTUALENVWRAPPER_VIRTUALENV=/usr/local/bin/virtualenv" >> ~/.bash_profile
grep -qxF "source /usr/local/bin/virtualenvwrapper.sh" ~/.bash_profile || echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bash_profile
source ~/.bash_profile

mkvirtualenv dataworkspace
grep -qxF "set -a" $WORKON_HOME/dataworkspace/bin/postactivate || echo "set -a" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "source /Users/yusufertekin/Sites/DIT/data-workspace/.env" $WORKON_HOME/dataworkspace/bin/postactivate || echo "source /Users/yusufertekin/Sites/DIT/data-workspace/.env" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "set +a" $WORKON_HOME/dataworkspace/bin/postactivate || echo "set +a" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export LC_ALL=en_US.UTF-8" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export LC_ALL=en_US.UTF-8" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export LANG=en_US.UTF-8" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export LANG=en_US.UTF-8" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export LANGUAGE=en_US.UTF-8" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export LANGUAGE=en_US.UTF-8" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export DJANGO_SETTINGS_MODULE=dataworkspace.settings.local" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export DJANGO_SETTINGS_MODULE=dataworkspace.settings.local" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export PYTHONPATH=$1/dataworkspace" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export PYTHONPATH=$1/dataworkspace" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export REDIS_URL=redis://localhost:6379/" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export REDIS_URL=redis://localhost:6379/" >> $WORKON_HOME/dataworkspace/bin/postactivate
source $WORKON_HOME/dataworkspace/bin/activate
pip install -r $1/requirements-dev.txt
