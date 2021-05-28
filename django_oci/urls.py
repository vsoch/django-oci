"""

Copyright (c) 2020, Vanessa Sochat

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""

from django.conf.urls import url
from django.urls import path
from django_oci import views
from django_oci import settings

app_name = "django_oci"


urlpatterns = [
    url(
        r"^auth/token/?$",
        views.GetAuthToken.as_view(),
        name="get_auth_token",
    ),
    # https://github.com/opencontainers/distribution-spec/blob/master/spec.md#api-version-check
    url(
        r"^%s/?$" % settings.URL_PREFIX,
        views.APIVersionCheck.as_view(),
        name="api_version_check",
    ),
    url(
        r"^%s/(?P<name>[a-z0-9\/-_]+(?:[._-][a-z0-9]+)*)/tags/list/?$"
        % settings.URL_PREFIX,
        views.ImageTags.as_view(),
        name="image_tags",
    ),
    # This is for a full digest reference
    # https://github.com/opencontainers/distribution-spec/blob/master/spec.md#pulling-an-image-manifest
    url(
        r"^%s/(?P<name>[a-z0-9\/-_]+(?:[._-][a-z0-9]+)*)/manifests/(?P<reference>[A-Za-z0-9_+.-]+:[A-Fa-f0-9]+)/?$"
        % settings.URL_PREFIX,
        views.ImageManifest.as_view(),
        name="image_manifest",
    ),
    # This is for a tag reference
    url(
        r"^%s/(?P<name>[a-z0-9\/-_]+(?:[._-][a-z0-9]+)*)/manifests/(?P<tag>[A-Za-z0-9_+.-]+)/?$"
        % settings.URL_PREFIX,
        views.ImageManifest.as_view(),
        name="image_manifest",
    ),
    url(
        r"^%s/(?P<name>[a-z0-9\/-_]+(?:[._-][a-z0-9]+)*)/blobs/uploads/?$"
        % settings.URL_PREFIX,
        views.BlobUpload.as_view(),
        name="blob_upload",
    ),
    # Listed twice, once with and once without trailing slash
    path(
        "%s/blobs/uploads/<path:session_id>/" % settings.URL_PREFIX,
        views.BlobUpload.as_view(),
        name="blob_upload",
    ),
    path(
        "%s/blobs/uploads/<path:session_id>" % settings.URL_PREFIX,
        views.BlobUpload.as_view(),
        name="blob_upload",
    ),
    # Also listed twice, once with and once without trailing slash
    path(
        "%s/<path:name>/blobs/<digest>" % settings.URL_PREFIX,
        views.BlobDownload.as_view(),
        name="blob_download",
    ),
    path(
        "%s/<path:name>/blobs/<digest>/" % settings.URL_PREFIX,
        views.BlobDownload.as_view(),
        name="blob_download",
    ),
]
