# django-oci

[![PyPI version](https://badge.fury.io/py/django-oci.svg)](https://badge.fury.io/py/django-oci)
![docs/assets/img/django-oci.png](docs/assets/img/django-oci.png)

Open Containers distribution API for Django. 

This repository serves a Django app that can be used to provide an opencontainers
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

See the [documentation](https://vsoch.github.io/django-oci/) or [getting started guide](https://vsoch.github.io/django-oci/docs/getting-started/) for more details about setup, and testing. An [example application](tests) is provided
and described in the getting started guide as well. The latest [conformance testing](https://vsoch.github.io/django-oci/conformance/) is provided as well.

## Many Thanks 

* [cookiecutter-djangopackage](https://github.com/pydanny/cookiecutter-djangopackage)
