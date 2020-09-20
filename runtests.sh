#!/bin/bash

python manage.py makemigrations django_oci
python manage.py makemigrations
python manage.py migrate
python manage.py migrate django_oci
python manage.py test --noinput
rm db-test.sqlite3
