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
import uuid
import os

logger = logging.getLogger(__name__)

# Default views to Authenticate
authenticated_views = [
    "django_oci.views.blobs.BlobUpload",
    "django_oci.views.blobs.BlobDownload",
    "django_oci.views.image.ImageTags",
    "django_oci.views.image.ImageManifest",
]

DEFAULTS = {
    # Url base prefix
    "URL_PREFIX": "v2",
    # Disable registry authentication
    "DISABLE_AUTHENTICATION": False,
    # Version of distribution spec
    "SPEC_VERSION": "1",
    # Repository permissions
    "PRIVATE_ONLY": False,
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
    # The number of seconds a token is valid (10 minutes)
    "TOKEN_EXPIRES_SECONDS": 600,
    # Disable deletion of an image by tag or manifest (default is not disabled)
    "DISABLE_TAG_MANIFEST_DELETE": False,
    # Default content type is application/octet-stream
    "DEFAULT_CONTENT_TYPE": "application/octet-stream",
    # Default views to put under authentication, given that DISABLE_AUTHENTICTION is False
    "AUTHENTICATED_VIEWS": authenticated_views,
    # If you have a custom authentication server to generate tokens (defaults to /registry/auth/token
    "AUTHENTICATION_SERVER": None,
    # jwt encoding secret: set server wide or generated on the fly
    "JWT_SERVER_SECRET": str(uuid.uuid4()),
    # View rate limit, defaults to 100/1day using django-ratelimit based on ipaddress
    "VIEW_RATE_LIMIT": "100/1d",
    # Given that someone goes over, are they blocked for a period?
    "VIEW_RATE_LIMIT_BLOCK": True,
}

# The user can define a section for DJANGO_OCI in settings
oci = getattr(settings, "DJANGO_OCI", DEFAULTS)

# Allows for import of variables above from django_oci.settings
URL_PREFIX = oci.get("URL_PREFIX", DEFAULTS["URL_PREFIX"])
DISABLE_AUTHENTICATION = oci.get(
    "DISABLE_AUTHENTICATION", DEFAULTS["DISABLE_AUTHENTICATION"]
)
AUTH_SERVER = oci.get("AUTHENTICATION_SERVER", DEFAULTS["AUTHENTICATION_SERVER"])
SPEC_VERSION = oci.get("SPEC_VERSION", DEFAULTS["SPEC_VERSION"])
PRIVATE_ONLY = oci.get("PRIVATE_ONLY", DEFAULTS["PRIVATE_ONLY"])
CONTENT_TYPES = oci.get("CONTENT_TYPES", DEFAULTS["CONTENT_TYPES"])
JWT_SERVER_SECRET = oci.get("JWT_SERVER_SECRET", DEFAULTS["JWT_SERVER_SECRET"])
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
TOKEN_EXPIRES_SECONDS = oci.get(
    "TOKEN_EXPIRES_SECONDS", DEFAULTS["TOKEN_EXPIRES_SECONDS"]
)
SESSION_EXPIRES_SECONDS = oci.get(
    "SESSION_EXPIRES_SECONDS", DEFAULTS["SESSION_EXPIRES_SECONDS"]
)
AUTHENTICATED_VIEWS = oci.get("AUTHENTICATED_VIEWS", DEFAULTS["AUTHENTICATED_VIEWS"])

# Rate Limits
VIEW_RATE_LIMIT = oci.get("VIEW_RATE_LIMIT", DEFAULTS["VIEW_RATE_LIMIT"])
VIEW_RATE_LIMIT_BLOCK = oci.get(
    "VIEW_RATE_LIMIT_BLOCK", DEFAULTS["VIEW_RATE_LIMIT_BLOCK"]
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

# Default auto field
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Create a filesystem cache for temporary upload sessions
cache = CACHE_DIR or os.path.join(MEDIA_ROOT, "cache")
if not os.path.exists(cache):
    logger.debug(f"Creating cache directory {cache}")
    os.makedirs(cache)

CACHES.update(
    {
        "django_oci_upload": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": os.path.abspath(cache),
        }
    }
)
