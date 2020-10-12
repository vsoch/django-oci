---
title: "Getting Started"
pdf: true
toc: true
---

# Getting Started

## Install

You might first want to install django-oci:

```bash
pip install django-oci
```

you could also install a development version from GitHub:

```bash
git clone https://github.com/vsoch/django-oci
cd django-oci

# To install to your python packages
pip install .

# To install from clone location
pip install -e .
```

This should install the one dependency, Django Rest Framework. If you want a requirements.txt
file to do the same, one is provided in the repository.

```bash
pip install -r reqiurements.txt
```

## Project Settings

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

You should also read about other [options]({{ site.baseurl }}/docs/getting-started/options)
to provide in your project settings to customize the registry, and see the [example application]({{ site.baseurl }}/docs/getting-started/example)
for an example of deployment. This will generate a distribution-spec set of API endpoints to generally push, pull,
and otherwise interact with a registry. What is not (yet) provided are frontend 
interfaces to see your containers.
