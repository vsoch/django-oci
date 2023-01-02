---
title: "Example Project"
pdf: true
toc: true
---

# Example Application

You can develop or test interactively using the example (very simple) application
under [tests](https://github.com/vsoch/django-oci/tree/master/tests).
First create a virtual environment with the dependencies
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

The [manage.py](https://github.com/vsoch/django-oci/blob/master/manage.py) is located in the root directory
so it's easy to update your install ad then interact with your test interface.

```bash
python manage.py makemigrations django_oci
python manage.py migrate django_oci
python manage.py runserver
```

See the [tests](https://github.com/vsoch/django-oci/tree/master/tests) folder for more details,
including how to start a development server. Examples will be added.
