#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_version(*file_paths):
    """Retrieves the version from django_oci/__init__.py"""
    filename = os.path.join(os.path.dirname(__file__), *file_paths)
    version_file = open(filename).read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


version = get_version("django_oci", "__init__.py")

with open("README.md") as fd:
    readme = fd.read()

setup(
    name="django-oci",
    version=version,
    description="""Open Containers distribution API for Django""",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Vanessa Sochat",
    author_email="vsochat@stanford.edu",
    url="https://github.com/vsoch/django-oci",
    packages=[
        "django_oci",
    ],
    include_package_data=True,
    install_requires=["djangorestframework", "pyjwt==1.7.1", "django-ratelimit==3.0.0"],
    license="Apache Software License 2.0",
    zip_safe=False,
    keywords="django-oci",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Framework :: Django :: 1.11",
        "Framework :: Django :: 2.1",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
)
