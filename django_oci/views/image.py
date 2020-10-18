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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, BrowsableAPIRenderer
from django.http.response import Http404, HttpResponse
from django.views.decorators.cache import never_cache

from django_oci.models import Repository, Image, get_image_by_tag
from django_oci import settings
from django_oci.storage import storage
from .parsers import ManifestRenderer
from .auth import get_token, get_challenge

import os

# from opencontainers.image.v1.manifest import Manifest
# from rest_framework import generics, serializers, viewsets, status
# from rest_framework.exceptions import PermissionDenied, NotFound
# from ratelimit.mixins import RatelimitMixin


class ImageTags(APIView):
    """Return a list of tags for an image."""

    permission_classes = []
    allowed_methods = ("GET",)

    @never_cache
    def get(self, request, *args, **kwargs):
        """GET /v2/<name>/tags/list. We don't require authentication to list tags,
           unless the repository is private.
        """
        name = kwargs.get("name")
        number = request.GET.get("n")
        last = request.GET.get("last")

        try:
            repository = Repository.objects.get(name=name)
        except Repository.DoesNotExist:
            raise Http404

        # If the repository is private, require authentication
        if repository.private:
            token = get_token(request)
            if not repository.has_view_permission(token.user):
                return Response(status=401, headers={"Www-Authenticate": get_challenge(repository.name, scopes="pull")})

        tags = [
            x
            for x in list(repository.image_set.values_list("tag__name", flat=True))
            if x
        ]

        # Tags must be sorted in lexical order
        tags.sort()

        # Number must be an integer if defined
        if number:
            number = int(number)

        # if last, <tagname> not included in the results, but up to <int> tags after <tagname> will be returned.
        if last and number:
            try:
                start = tags.index(last)
            except IndexError:
                start = 0
            tags = tags[start:number]

        elif number:
            tags = tags[:number]

        # Ensure tags sorted in lexical order
        data = {"name": repository.name, "tags": sorted(tags)}
        return Response(status=200, data=data)


class ImageManifest(APIView):
    """An Image Manifest holds the configuration and metadata about an image
    GET: is to retrieve an existing image manifest
    PUT: is to push a manifest
    """

    renderer_classes = [ManifestRenderer, JSONRenderer]
    permission_classes = []
    allowed_methods = (
        "GET",
        "PUT",
        "DELETE",
    )

    @never_cache
    def delete(self, request, *args, **kwargs):
        """DELETE /v2/<name>/manifests/<tag>"""

        # A registry must globally disable or enable both
        if settings.DISABLE_TAG_MANIFEST_DELETE:
            return Response(status=405)

        name = kwargs.get("name")
        reference = kwargs.get("reference")
        tag = kwargs.get("tag")

        from django_oci.models import Tag

        # Retrieve the image, return of None indicates not found
        image = get_image_by_tag(name, reference=reference, tag=tag, create=False)
        if not image:
            raise Http404

        # Delete the image tag
        if tag:
            tag = image.tag_set.filter(name=tag)
            tag.delete()

        # Delete a manifest
        elif reference:
            image.delete()

        # Upon success, the registry MUST respond with a 202 Accepted code.
        return Response(status=202)

    @never_cache
    def put(self, request, *args, **kwargs):
        """PUT /v2/<name>/manifests/<reference>
        https://github.com/opencontainers/distribution-spec/blob/master/spec.md#pushing-manifests
        """
        # We likely can default to the v1 manifest, unless otherwise specified
        # application/vnd.oci.image.manifest.v1+json
        content_type = request.META.get(
            "CONTENT_TYPE", settings.IMAGE_MANIFEST_CONTENT_TYPE
        )

        name = kwargs.get("name")
        reference = kwargs.get("reference")
        tag = kwargs.get("tag")

        # Reference must be sha256 digest
        if reference and not reference.startswith("sha256:"):
            return Response(status=400)

        # Also provide the body in case we have a tag
        image = get_image_by_tag(name, reference, tag, create=True, body=request.body)
        return Response(status=201, headers={"Location": image.get_manifest_url()})

    @never_cache
    def get(self, request, *args, **kwargs):
        """GET /v2/<name>/manifests/<reference>"""

        name = kwargs.get("name")
        reference = kwargs.get("reference")
        tag = kwargs.get("tag")

        image = get_image_by_tag(name, tag=tag, reference=reference)

        # If the manifest is not found in the registry, the response code MUST be 404 Not Found.
        if not image:
            raise Http404
        return Response(image.manifest, status=200)
