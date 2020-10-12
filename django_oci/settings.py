"""

Copyright (C) 2020 Vanessa Sochat.

This Source Code Form is subject to the terms of the
Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.

Settings are namespaced to the DJANGO_OCI namespace. Any of the following
below can be overridden in the default django settings, e.g.:

DJANGO_OCI = {
    'SPEC_VERSION': "v2",
    'PRIVATE_ONLY': False
}

"""

from django.conf import settings
import logging
import os

logger = logging.getLogger(__name__)

DEFAULTS = {
    # Url base prefix
    "URL_PREFIX": "v2",
    # Version of distribution spec
    "SPEC_VERSION": "1",
    # Repository permissions
    "PRIVATE_ONLY": False,
    # Authentication (only defined if custom user class)
    "AUTHENTICATED_USER": None,
    # Allowed content types to upload as layers
    "CONTENT_TYPES": ["application/octet-stream"],
    # Image Manifest content type
    "IMAGE_MANIFEST_CONTENT_TYPE": "application/vnd.oci.image.manifest.v1+json",
    # Storage backend
    "STORAGE_BACKEND": "filesystem",
    # Domain used in templates, api prefix
    "DOMAIN_URL": "http://127.0.0.1:8000",
    # Media root (if saving images on filesystem
    "MEDIA_ROOT": "images",
    # Set a cache directory, otherwise defaults to MEDIA_ROOT + /cache
    "CACHE_DIR": None,
    # The number of seconds a session (upload request) is valid (10 minutes)
    "SESSION_EXPIRES_SECONDS": 600,
    # Disable deletion of an image by tag or manifest (default is not disabled)
    "DISABLE_TAG_MANIFEST_DELETE": False,
    # Default content type is application/octet-stream
    "DEFAULT_CONTENT_TYPE": "application/octet-stream",
}

# The user can define a section for DJANGO_OCI in settings
oci = getattr(settings, "DJANGO_OCI", DEFAULTS)

# Allows for import of variables above from django_oci.settings
URL_PREFIX = oci.get("URL_PREFIX", DEFAULTS["URL_PREFIX"])
SPEC_VERSION = oci.get("SPEC_VERSION", DEFAULTS["SPEC_VERSION"])
PRIVATE_ONLY = oci.get("PRIVATE_ONLY", DEFAULTS["PRIVATE_ONLY"])
AUTHENTICATED_USER = oci.get("AUTHENTICATED_USER", DEFAULTS["AUTHENTICATED_USER"])
CONTENT_TYPES = oci.get("CONTENT_TYPES", DEFAULTS["CONTENT_TYPES"])
STORAGE_BACKEND = oci.get("STORAGE_BACKEND", DEFAULTS["STORAGE_BACKEND"])
DOMAIN_URL = oci.get("DOMAIN_URL", DEFAULTS["DOMAIN_URL"])
MEDIA_ROOT = oci.get("MEDIA_ROOT", DEFAULTS["MEDIA_ROOT"])
CACHE_DIR = oci.get("CACHE_DIR", DEFAULTS["CACHE_DIR"])
DEFAULT_CONTENT_TYPE = oci.get("DEFAULT_CONTENT_TYPE", DEFAULTS["DEFAULT_CONTENT_TYPE"])
IMAGE_MANIFEST_CONTENT_TYPE = oci.get(
    "IMAGE_MANIFEST_CONTENT_TYPE", DEFAULTS["IMAGE_MANIFEST_CONTENT_TYPE"]
)
DISABLE_TAG_MANIFEST_DELETE = oci.get(
    "DISABLE_TAG_MANIFEST_DELETE", DEFAULTS["DISABLE_TAG_MANIFEST_DELETE"]
)

SESSION_EXPIRES_SECONDS = oci.get(
    "SESSION_EXPIRES_SECONDS", DEFAULTS["SESSION_EXPIRES_SECONDS"]
)

# Set filesystem cache, also adding to middleware
CACHES = getattr(settings, "CACHES", {})
MIDDLEWARE = getattr(settings, "MIDDLEWARE", [])

for entry in [
    "django.middleware.cache.UpdateCacheMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.cache.FetchFromCacheMiddleware",
]:
    if entry not in MIDDLEWARE:
        MIDDLEWARE.append(entry)

# Create a filesystem cache for temporary upload sessions
cache = CACHE_DIR or os.path.join(MEDIA_ROOT, "cache")
if not os.path.exists(cache):
    logger.debug(f"Creating cache directory {cache}")
    os.makedirs(cache)

CACHES.update(
    {
        "django_oci_upload": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": cache,
        }
    }
)
