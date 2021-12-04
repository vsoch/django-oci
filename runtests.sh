#!/bin/bash

function setup {
  python manage.py makemigrations django_oci
  python manage.py makemigrations
  python manage.py migrate
  python manage.py migrate django_oci
}

function cleanup {
  rm db-test.sqlite3
}

# Test the API with authentication
#setup
#python manage.py test tests.test_api
#cleanup

# Test conformance without authentication
setup
DISABLE_AUTHENTICATION=yes python manage.py test tests.test_conformance
cleanup

# python manage.py test --noinput
