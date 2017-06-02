#!/bin/bash

cd $(echo $0 | sed 's#/[^/]*$##')/..
source /usr/local/bin/virtualenvwrapper.sh
workon proffoi

git pull > /tmp/load_prof_foi.tmp 2>&1

bin/scrap.py >> /tmp/load_prof_foi.tmp 2>&1

if git status | grep "documents/" > /dev/null; then
  cat /tmp/load_prof_foi.tmp
  git commit documents -m "autoupdate"
  git push
fi
