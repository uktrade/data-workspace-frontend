#!/bin/bash
set -e

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

echo 'debug: install postgres'
if brew ls --versions postgres > /dev/null; then
    # package already installed
    echo 'postgres already installed'
   
else
    # The package is not installed
    brew install postgres
fi

if brew services list | cut -d ' ' -f 1 | grep -qw postgresql > /dev/null; then
    # postgres is running already
    echo 'postgres already running'
else
    # start postgres
    pg_ctl -D /usr/local/var/postgres start
fi

if psql -lqt | cut -d \| -f 1 | grep -qw dataworkspace > /dev/null; then
    # dataworkspace already exists
    echo 'dataworkspace database already exists'
else
    createdb dataworkspace
fi

echo 'debug: install redis'
brew install redis
echo 'debug: start redis'
brew services start redis
echo 'debug: pip install virtualenv'
pip install virtualenv
echo 'debug: pip install virtualenvwrapper'
pip install virtualenvwrapper

# needed for virtualenvwrapper
echo 'debug: update .bash_profile'
grep -qF "WORKON_HOME" ~/.bash_profile || echo "export WORKON_HOME=~/.virtualenvs" >> ~/.bash_profile

# python binary
grep -qxF "export VIRTUALENVWRAPPER_PYTHON=/Users/dvoong/anaconda3/bin/python3" ~/.bash_profile || echo "export VIRTUALENVWRAPPER_PYTHON=/Users/dvoong/anaconda3/bin/python3" >> ~/.bash_profile

# set virtualenv bin
# grep -qxF "export VIRTUALENVWRAPPER_VIRTUALENV=/usr/local/bin/virtualenv" ~/.bash_profile || echo "export VIRTUALENVWRAPPER_VIRTUALENV=/usr/local/bin/virtualenv" >> ~/.bash_profile
grep -qxF "export VIRTUALENVWRAPPER_VIRTUALENV=/Users/dvoong/anaconda3/bin/virtualenv" ~/.bash_profile || echo "export VIRTUALENVWRAPPER_VIRTUALENV=/Users/dvoong/anaconda3/bin/virtualenv" >> ~/.bash_profile

# set virtualenv bin
#grep -qxF "source /usr/local/bin/virtualenvwrapper.sh" ~/.bash_profile || echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bash_profile
grep -qxF "source /Users/dvoong/anaconda3/bin/virtualenvwrapper.sh" ~/.bash_profile || echo "source /Users/dvoong/anaconda3/bin/virtualenvwrapper.sh" >> ~/.bash_profile

echo 'debug: source .bash_profile'
source ~/.bash_profile

echo 'debug: mkvirtualenv dataworkspace'
if lsvirtualenv | grep -qw dataworkspace > /dev/null; then
    # virtualenv already exists
    echo 'dataworkspace env already exists'
else
    mkvirtualenv dataworkspace
fi
# set postactivate
echo 'debug: update postactivate'
echo 'debug: set -a'
grep -qxF "set -a" $WORKON_HOME/dataworkspace/bin/postactivate || echo "set -a" >> $WORKON_HOME/dataworkspace/bin/postactivate

# add environment variables to the postactivate script
echo 'debug: set environment files'
# grep -qxF "source /Users/yusufertekin/Sites/DIT/data-workspace/.env" $WORKON_HOME/dataworkspace/bin/postactivate || echo "source /Users/yusufertekin/Sites/DIT/data-workspace/.env" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "source /Users/dvoong/projects/dit/data-workspace/.env" $WORKON_HOME/dataworkspace/bin/postactivate || echo "source /Users/dvoong/projects/dit/data-workspace/.env" >> $WORKON_HOME/dataworkspace/bin/postactivate

echo 'debug: set+a'
grep -qxF "set +a" $WORKON_HOME/dataworkspace/bin/postactivate || echo "set +a" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export LC_ALL=en_US.UTF-8" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export LC_ALL=en_US.UTF-8" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export LANG=en_US.UTF-8" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export LANG=en_US.UTF-8" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export LANGUAGE=en_US.UTF-8" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export LANGUAGE=en_US.UTF-8" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export DJANGO_SETTINGS_MODULE=dataworkspace.settings.local" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export DJANGO_SETTINGS_MODULE=dataworkspace.settings.local" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export PYTHONPATH=$1/dataworkspace" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export PYTHONPATH=$1/dataworkspace" >> $WORKON_HOME/dataworkspace/bin/postactivate
grep -qxF "export REDIS_URL=redis://localhost:6379/" $WORKON_HOME/dataworkspace/bin/postactivate || echo "export REDIS_URL=redis://localhost:6379/" >> $WORKON_HOME/dataworkspace/bin/postactivate
echo 'debug: activate virtual environment'
echo "$WORKON_HOME/dataworkspace/bin/activate"
source $WORKON_HOME/dataworkspace/bin/activate
echo 'debug: pip install requirements'
pip install -r $1/requirements/dev.txt
