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

from django.urls import reverse
from django.conf.urls import url
from django.urls import path
from .routers import urlpatterns as router_patterns
from django_oci import views
from django_oci import settings

app_name = 'django_oci'


urlpatterns = [

    # https://github.com/opencontainers/distribution-spec/blob/master/spec.md#api-version-check
    url(r"^%s/?$" % settings.URL_PREFIX, views.APIVersionCheck.as_view(), name="api-version-check"),

    # https://github.com/opencontainers/distribution-spec/blob/master/spec.md#pulling-an-image-manifest
    url(
        r"^%s/(?P<name>[a-z0-9\/]+(?:[._-][a-z0-9]+)*)/manifests/(?P<reference>[A-Za-z0-9_+.-]+:[A-Fa-f0-9]+)/?$" % settings.URL_PREFIX,
        views.ImageManifest.as_view(),
    ),

    url(
        r"^%s/(?P<name>[a-z0-9\/]+(?:[._-][a-z0-9]+)*)/blobs/uploads/?$" % settings.URL_PREFIX,
        views.ImageBlobUpload.as_view(),
    ),

    path('%s/<path:name>/blobs/download/<digest>/' % settings.URL_PREFIX, views.ImageBlobDownload.as_view(), name="image_blob_download"),
    path('%s/<path:session_id>/blobs/upload/' % settings.URL_PREFIX, views.ImageBlobUpload.as_view(), name="image_blob_upload"),

    path('', views.ChunkedUploadDemo.as_view(), name='chunked_upload'),
    path('api/chunked_upload_complete/', views.MyChunkedUploadCompleteView.as_view(), name='api_chunked_upload_complete'),
    path('api/chunked_upload/', views.MyChunkedUploadView.as_view(), name='api_chunked_upload'),

] + router_patterns

#    url(
#        r"^container/search/collection/(?P<collection>.+?)/name/(?P<name>.+?)/?$",
#        ContainerSearch.as_view(),
#    ),
#    url(
#        r"^container/search/name/(?P<name>.+?)/tag/(?P<tag>.+?)/?$",
#        ContainerSearch.as_view(),
#    ),
#    url(r"^container/search/name/(?P<name>.+?)/?$", ContainerSearch.as_view()),
#    url(
#        r"^container/(?P<collection>.+?)/(?P<name>.+?):(?P<tag>.+?)@(?P<version>.+?)/?$",
#        ContainerDetailByName.as_view(),
#    ),
#    url(
#        r"^container/(?P<collection>.+?)/(?P<name>.+?)@(?P<version>.+?)/?$",
#       ContainerDetailByName.as_view(),
#    ),
#    url(
#        r"^container/(?P<collection>.+?)/(?P<name>.+?):(?P<tag>.+?)/?$",
#        ContainerDetailByName.as_view(),
#    ),
#    url(
#        r"^container/(?P<collection>.+?)/(?P<name>.+?)/?$",
#        ContainerDetailByName.as_view(),
#    ),
#] + router_patterns
