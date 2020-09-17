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
from django_oci.models import Repository, Image
from django_oci import settings
from django.middleware import cache

from opencontainers.image.v1.manifest import Manifest
from django_oci.storage import get_storage
from django_oci.utils import parse_content_range

import os


# from rest_framework import generics, serializers, viewsets, status
# from rest_framework.exceptions import PermissionDenied, NotFound
# from ratelimit.mixins import RatelimitMixin

# Load storage on application init
storage = get_storage()


class ImageBlobDownload(APIView):
    """Given a GET request for a blob, stream the blob."""

    permission_classes = []
    allowed_methods = ("GET",)

    def get(self, request, *args, **kwargs):
        """POST /v2/<name>/blobs/download/<digest>"""

        name = kwargs.get("name")
        digest = kwargs.get("digest")
        return storage.download_blob(name, digest)


class ImageTags(APIView):
    """Return a list of tags for an image."""

    permission_classes = []
    allowed_methods = ("GET",)

    def get(self, request, *args, **kwargs):
        """GET /v2/<name>/tags/list"""
        name = kwargs.get("name")
        number = request.GET.get("n")
        tags = list(repository.image_set.values_list("tag", flat=True))
        if number:
            tags = tags[:number]

        # Ensure the repository exists
        try:
            repository = Repository.objects.get(name=name)
        except Repository.DoesNotExist:
            raise Http404

        # Ensure tags sorted in lexical order
        data = {"name": repository.name, "tags": sorted(tags)}
        return Response(status=200, data=data)


class ImageBlobUpload(APIView):
    """An image push will receive a request to push, authenticate the user,
    and return an upload url (url is /v2/<name>/blobs/uploads/)
    """

    permission_classes = []
    allowed_methods = ("POST", "PUT", "PATCH")

    def put(self, request, *args, **kwrags):
        """A put request can happen in two scenarios. 1. after a POST request,
        and must include a session_id. The session id is created via the file
        system cache, and each one includes the request type, image id
        (associated with a tag), repository, and a randomly generated uuid.
        The upload will not continue if any required metadata is missing or
        the identifier is already expired. The second case is after several
        PATCH requests to upload chunks of a blob. The final chunk might be
        provided this case.
        """
        # These header attributes are shared by both scenarios
        session_id = kwargs.get("session_id")
        digest = request.GET.get("digest")
        content_length = int(request.META.get("CONTENT_LENGTH"))
        content_type = request.META.get("CONTENT_TYPE")

        # Presence of content range distinguishes chunked upload from single PUT
        content_range = request.META.get("CONTENT_RANGE")

        if not session_id or not digest or not content_length or not content_type:
            return Response(status=400)

        # Confirm that content length (body) == header value, otherwise bad request
        if len(request.body) != content_length:
            return Response(status=400)

        # Get the session id, if it has not expired
        filecache = cache.caches["django_oci_upload"]
        if not filecache.get(session_id):
            return Response(status=400)

        # Ensure it cannot be used again
        filecache.set(session_id, None, timeout=0)

        # Break apart into repository name, image id, and uuid
        _, collection, image_id, _ = session_id.split("/")
        try:
            repository = Repository.objects.get(name=collection)
            image = Image.objects.get(id=image_id)
        except (Repository.DoesNotExist, Image.DoesNotExist):
            return Response(status=404)

        # Scenario 1: a single PUT request
        if not content_range and request.body:

            # Now process the PUT request to the file!
            return storage.create_blob(
                name=repository.name,
                body=request.body,
                digest=digest,
                content_type=content_type,
            )

        # Scenario 2: a PUT to end a chunked upload session, no final chunk
        # TODO how do we ensure that the session_id gets us the correct blob?
        elif not request.body:
            return storage.finish_blob(
                name=repository.name,
                digest=digest,
                session_id=session_id,
            )

        # Scenario 3: a PUT to end a chunked upload session with a final chunk
        # First ensure upload session cannot be used again
        filecache.set(session_id, None, timeout=0)

        # Parse the start and end for the chunk to write
        try:
            content_start, content_end = parse_content_range(content_range)
        except ValueError:
            return Response(status=400)

        # The session_id is used to find the blob
        return storage.finish_blob(
            image=image,
            digest=digest,
        )

    def patch(self, request, *args, **kwargs):
        """a patch request is done after a POST with content-length 0 to indicate
        a chunked upload request.
        POST /v2/<name>/blobs/uploads/
        """
        session_id = kwargs.get("session_id")
        content_length = int(request.META.get("CONTENT_LENGTH"))
        content_range = int(request.META.get("CONTENT_RANGE"))
        content_type = request.META.get("CONTENT_TYPE")

        if (
            not session_id
            or not content_range
            or not content_length
            or not content_type
        ):
            return Response(status=400)

        # Parse content range into start and end (int)
        try:
            content_start, content_end = parse_content_range(content_range)
        except ValueError:
            return Response(status=400)

        # Confirm that content length (body) == header value, otherwise bad request
        if len(request.body) != content_length:
            return Response(status=400)

        # Get the session id, if it has not expired, keep open for next
        filecache = cache.caches["django_oci_upload"]
        if not filecache.get(session_id):
            return Response(status=400)

        # Break apart into repository name, image id, and uuid
        _, collection, image_id, _ = session_id.split("/")
        try:
            repository = Repository.objects.get(name=collection)
            image = Image.objects.get(id=image_id)
        except (Repository.DoesNotExist, Image.DoesNotExist):
            return Response(status=404)

        # Now process the PATCH request to upload the chunk
        return storage.upload_blob_chunk(
            repository=repository,
            image=image,
            session_id=session_id,
            body=request.body,
            content_type=content_type,
            content_start=content_start,
            content_end=content_end,
            content_length=content_length,
        )

        # TODO: close the session
        # Close the  session (PUT)

    def post(self, request, *args, **kwargs):
        """POST /v2/<name>/blobs/uploads/"""

        name = kwargs.get("name")

        # For check media type and content length (if needed)
        content_length = int(request.META.get("CONTENT_LENGTH"))
        content_type = request.META.get("CONTENT_TYPE")

        # If no content length, tell the user it's required
        if not content_length:
            return Response(status=411)

        # Unsupported media type
        if content_type not in settings.CONTENT_TYPES:
            return Response(status=415)

        # Case 1: POST provided with digest == single monolithic upload
        # /v2/<name>/blobs/uploads/?digest=<digest>
        if "digest" in request.GET:
            digest = request.GET["digest"]

            # Confirm that content length (body) == header value, otherwise bad request
            if len(request.body) != content_length:
                return Response(status=400)

            # The storage.create_blob handles creation of blob with body (no second request required)
            return storage.create_blob(
                name=name, body=request.body, digest=digest, content_type=content_type
            )

        # Case 2; Content type length 0 indicates chunked upload
        elif content_length != 0:
            return storage.create_blob_request(name=name)

        # Case 3: POST without digest == single monolithic with POST then PUT
        # returns a session location to upload to with PUT
        return storage.create_blob_request(name=name)


class ImageManifest(APIView):
    """An Image Manifest holds the configuration and metadata about an image
    GET: is to retrieve an existing image manifest
    PUT: is to push a manifest
    """

    permission_classes = []
    allowed_methods = (
        "GET",
        "PUT",
    )

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

        # Ensure the repository exists
        try:
            repository = Repository.objects.get(name=name)
        except Repository.DoesNotExist:
            raise Http404

        # reference can be a tag (more likely) or digest
        try:
            image = repository.image_set.get(tag=reference)
        except Repository.DoesNotExist:
            try:
                image = repository.image_set.get(version=reference)
            except:
                raise Http404

        # The manifest is in the body, load to string
        manifest = request.body.decode("utf-8")
        image.manifest = manifest
        image.save()

        # TODO: do we want to parse or otherwise load the manifest?
        # parse annotations
        # validate layers?
        return Response(status=201, headers={"Location": image.get_manifest_url()})

    def get(self, request, *args, **kwargs):
        """GET /v2/<name>/manifests/<reference>"""

        name = kwargs.get("name")
        reference = kwargs.get("reference")

        # TODO check for header and see if we can filter down to types
        # The client SHOULD include an Accept header indicating which manifest content types it supports. In a successful response, the Content-Type header will indicate which manifest type is being returned.

        # Does the repository exist?
        try:
            repo = Repository.objects.get(name=name)
        except Repository.DoesNotExist:
            raise Http404

        # Does the reference (tag or version) exist?
        try:
            image = repo.image_set.get(tag=reference)
        except Repository.DoesNotExist:
            try:
                image = repo.image_set.get(version=reference)
            except:
                raise Http404

        print(request.body)
        print(image)

        # Create and validate a manifest
        manifest = Manifest()
        manifest.load()

        headers = {"Docker-Distribution-API-Version": "registry/2.0"}
        return Response(manifest.to_dict())
