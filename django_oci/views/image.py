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
from django.http.response import Http404, HttpResponse
from django_oci.models import Repository, Image, get_image_by_tag
from django_oci import settings
from django_oci.storage import storage

import os

# from opencontainers.image.v1.manifest import Manifest
# from rest_framework import generics, serializers, viewsets, status
# from rest_framework.exceptions import PermissionDenied, NotFound
# from ratelimit.mixins import RatelimitMixin


class ImageTags(APIView):
    """Return a list of tags for an image."""

    permission_classes = []
    allowed_methods = ("GET",)

    def get(self, request, *args, **kwargs):
        """GET /v2/<name>/tags/list"""
        name = kwargs.get("name")
        number = request.GET.get("n")

        try:
            repository = Repository.objects.get(name=name)
        except Repository.DoesNotExist:
            raise Http404

        tags = [
            x
            for x in list(repository.image_set.values_list("tag__name", flat=True))
            if x
        ]
        if number:
            tags = tags[:number]

        # Ensure tags sorted in lexical order
        data = {"name": repository.name, "tags": sorted(tags)}
        return Response(status=200, data=data)


class ImageManifest(APIView):
    """An Image Manifest holds the configuration and metadata about an image
    GET: is to retrieve an existing image manifest
    PUT: is to push a manifest
    """

    permission_classes = []
    allowed_methods = (
        "GET",
        "PUT",
        "DELETE",
    )

    def delete(self, request, *args, **kwargs):
        """DELETE /v2/<name>/manifests/<tag>"""

        # A registry must globally disable or enable both
        if settings.DISABLE_TAG_MANIFEST_DELETE:
            return Response(status=405)

        name = kwargs.get("name")
        reference = kwargs.get("reference")
        tag = kwargs.get("tag")

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

    def put(self, request, *args, **kwargs):
        """PUT /v2/<name>/manifests/<reference>
        https://github.com/opencontainers/distribution-spec/blob/master/spec.md#pushing-manifests
        """
        # We likely can default to the v1 manifest, unless otherwise specified
        content_type = request.META.get(
            "CONTENT_TYPE", "application/vnd.oci.image.manifest.v1+json"
        )
        name = kwargs.get("name")
        reference = kwargs.get("reference")
        tag = kwargs.get("tag")
        image = get_image_by_tag(name, reference, tag, create=True)

        # The manifest is in the body, load to string
        manifest = request.body.decode("utf-8")
        image.save_manifest(manifest)

        # Load the manifest to get blob associations
        manifest = image.get_manifest()

        # TODO: do we want to parse or otherwise load the manifest?
        # parse annotations
        # validate layers?
        return Response(status=201, headers={"Location": image.get_manifest_url()})

    def get(self, request, *args, **kwargs):
        """GET /v2/<name>/manifests/<reference>"""

        name = kwargs.get("name")
        reference = kwargs.get("reference")

        image = get_image_by_tag(name, tag=reference)
        if not image:
            raise Http404

        # TODO check for header and see if we can filter down to types
        # The client SHOULD include an Accept header indicating which manifest content types it supports. In a successful response, the Content-Type header will indicate which manifest type is being returned.

        print(request.body)
        print(image)

        # Create and validate a manifest
        manifest = Manifest()
        manifest.load()

        headers = {"Docker-Distribution-API-Version": "registry/2.0"}
        return Response(manifest.to_dict())
