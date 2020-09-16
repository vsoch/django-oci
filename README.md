# django-oci

![https://badge.fury.io/py/django-oci.svg](https://badge.fury.io/py/django-oci)
![https://travis-ci.org/vsoch/django-oci.svg?branch=master](https://travis-ci.org/vsoch/django-oci)
![https://codecov.io/gh/vsoch/django-oci/branch/master/graph/badge.svg](https://codecov.io/gh/vsoch/django-oci)

Open Containers distribution API for Django. 

**under development**

> Not all files are added yet to this repository, so it will not work! This readme will be updated when all is ready.

This repository will serve a Django app that can be used to provide an opencontainers
distribution (OCI) endpoint to push and pull containers. An [example](tests)
application is provided in `tests` that can be interacted with here.

## Quickstart

Install django-oci::

```bash
pip install django-oci
```

Add it to your `INSTALLED_APPS` along with `rest_framework`

```python

    INSTALLED_APPS = (
        ...
        'django_oci',
        'rest_framework',
        'chunked_upload',
        ...
    )
```

Add django-oci's URL patterns:

```python

    from django_oci import urls as django_oci_urls
    urlpatterns = [
        ...
        url(r'^', include(django_oci.urls)),
        ...
    ]

```

### Example Application

You can develop or test interactively using the example (very simple) application
under [tests](tests). First create a virtual environment with the dependencies
that you need:

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

For development you can install the `django_oci` module locally:

```bash
$ pip install -e .
```

The [manage.py](manage.py) is located in the root directory
so it's easy to update your install ad then interact with your test interface.

```bash
python manage.py makemigrations django_oci
python manage.py migrate django_oci
python manage.py runserver
```

### Authentication

**todo**

### Push a Container

When your server is running with `python manage.py runserver` then you can try pushing
a container with the provided script [push-container.py](push-container.py)

```bash
# Obtain a container
singularity pull docker://busybox

# Push it
python push-container.py busybox_latest.sif vanessa/test:latest
```

The push script uses a Multipart upload to interact with the API.

## Testing

Tests are located in [tests](tests) and can be run with:

```bash
python runtests.py
```


## Running Tests

Does the code actually work?

```bash
source <YOURVIRTUALENV>/bin/activate
(myenv) $ pip install tox
(myenv) $ tox


## Many Thanks 


* [cookiecutter-djangopackage](https://github.com/pydanny/cookiecutter-djangopackage)
