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


class BlobDownload(APIView):
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



class BlobUpload(APIView):
    """An image push will receive a request to push, authenticate the user,
    and return an upload url (url is /v2/<name>/blobs/uploads/)
    """

    permission_classes = []
    allowed_methods = ("POST", "PUT", "PATCH")

    def put(self, request, *args, **kwrags):
        """PUT /v2/<name>/blobs/uploads/
        A put request can happen in two scenarios. 1. after a POST request,
        and must include a session_id. The session id is created via the file
        system cache, and each one includes the request type, image id
        (associated with a tag), repository, and a randomly generated uuid.
        The upload will not continue if any required metadata is missing or
        the identifier is already expired. The second case is after several
        PATCH requests to upload chunks of a blob. The final chunk might be
        provided this case.
        """
        # These header attributes are shared by both scenarios
        name = kwargs.get("name")
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

        # Break apart into blob id, and session uuid (version)
        _, blob_id, version = session_id.split("/")
        try:
            blob = Blob.objects.get(id=blob_id, version=version)
        except (Blob.DoesNotExist):
            return Response(status=404)

        # Scenario 1: a single PUT request
        if not content_range and request.body:

            # Now process the PUT request to the file! Provide the blob to update
            return storage.create_blob(
                blob=blob,
                name=name,
                body=request.body,
                digest=digest,
                content_type=content_type,
            )

        # Scenario 2: a PUT to end a chunked upload session, no final chunk
        elif not request.body:
            return storage.finish_blob(
                blob=blob,
                name=name,
                digest=digest,
            )

        # Scenario 3: a PUT to end a chunked upload session with a final chunk
        # First ensure upload session cannot be used again
        filecache.set(session_id, None, timeout=0)

        # Parse the start and end for the chunk to write
        try:
            content_start, content_end = parse_content_range(content_range)
        except ValueError:
            return Response(status=400)

        # Write the final chunk and finish the session
        status_code = blob.write_chunk(content_start=content_start, content_end=content_end, body=request.body)

        # If it's already existing, return Accepted header, otherwise alert created
        if status_code != 202:
            return Response(status=status_code)

        return storage.finish_blob(
            blob=blob,
            name=name,
            digest=digest,
        )


    def patch(self, request, *args, **kwargs):
        """a patch request is done after a POST with content-length 0 to indicate
        a chunked upload request.
        POST /v2/<name>/blobs/uploads/
        """
        name = kwargs.get("name")
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

        # Break apart into blob id and session uuid
        _, blob_id, version = session_id.split("/")
        try:
            blob = Blob.objects.get(id=blob_id, version=version)
        except Blob.DoesNotExist:
            return Response(status=404)

        # Update the blob content_type TODO: There should be some check
        # to ensure that a next chunk content type is not different from that
        # already defined
        blob.content_type = content_type

        # Now process the PATCH request to upload the chunk
        return storage.upload_blob_chunk(
            blob=blob,
            name=name,
            body=request.body,
            content_start=content_start,
            content_end=content_end,
            content_length=content_length,
        )

    def post(self, request, *args, **kwargs):
        """POST /v2/<name>/blobs/uploads/"""

        # the name is only used to validate the user has permission to upload
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
            # We only pass the name to return it with the blob's download url, there is no association
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
        "DELETE",
    )

    def delete(self, request, *args, **kwargs):
        """DELETE /v2/<name>/manifests/<tag>"""

        # A registry must globally disable or enable both
        if not settings.DISABLE_TAG_MANIFEST_DELETE:
            return Response(status=405)

        name = kwargs.get("name")
        reference = kwargs.get("reference")

        # Retrieve the image, return of None indicates not found
        if not (image =: get_image_by_tag(name, reference)):
            raise Http404
        
        # Delete the image
        # TODO: need to test case that image has multiple tags
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
        if not (image =: get_image_by_tag(name, reference)):
            raise Http404

        # The manifest is in the body, load to string
        manifest = request.body.decode("utf-8")
        image.manifest = manifest
        image.save()

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

        if not (image =: get_image_by_tag(name, reference)):
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
