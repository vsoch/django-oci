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
from django.views.decorators.cache import never_cache

from django_oci.models import Blob, Repository
from django_oci import settings
from django_oci.storage import storage
from django.middleware import cache

from django_oci.utils import parse_content_range
from django_oci.auth import is_authenticated
from django.shortcuts import get_object_or_404

from ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator


class BlobDownload(APIView):
    """Given a GET request for a blob, stream the blob."""

    permission_classes = []
    allowed_methods = (
        "GET",
        "DELETE",
        "HEAD",
    )

    @never_cache
    @method_decorator(
        ratelimit(
            key="ip",
            rate=settings.VIEW_RATE_LIMIT,
            method="GET",
            block=settings.VIEW_RATE_LIMIT_BLOCK,
        )
    )
    def get(self, request, *args, **kwargs):
        """POST /v2/<name>/blobs/<digest>"""
        # the name is only used to validate the user has permission to upload
        name = kwargs.get("name")
        digest = kwargs.get("digest")

        # If allow_continue False, return response
        allow_continue, response, _ = is_authenticated(request, name, scopes=["pull"])
        if not allow_continue:
            return response

        return storage.download_blob(name, digest)

    @never_cache
    @method_decorator(
        ratelimit(
            key="ip",
            rate=settings.VIEW_RATE_LIMIT,
            method="DELETE",
            block=settings.VIEW_RATE_LIMIT_BLOCK,
        )
    )
    def delete(self, request, *args, **kwargs):
        """DELETE /v2/<name>/blobs/<digest>"""
        name = kwargs.get("name")
        digest = kwargs.get("digest")

        # If allow_continue False, return response
        allow_continue, response, _ = is_authenticated(
            request, name, must_be_owner=True
        )
        if not allow_continue:
            return response

        return storage.delete_blob(name, digest)

    @never_cache
    @method_decorator(
        ratelimit(
            key="ip",
            rate=settings.VIEW_RATE_LIMIT,
            method="HEAD",
            block=settings.VIEW_RATE_LIMIT_BLOCK,
        )
    )
    def head(self, request, *args, **kwargs):
        """HEAD /v2/<name>/blobs/<digest>"""
        name = kwargs.get("name")
        digest = kwargs.get("digest")

        # If allow_continue False, return response
        allow_continue, response, _ = is_authenticated(
            request, name, must_be_owner=True
        )
        if not allow_continue:
            return response

        # A HEAD request to an existing blob or manifest URL MUST return 200 OK.
        return storage.blob_exists(name, digest)


class BlobUpload(APIView):
    """An image push will receive a request to push, authenticate the user,
    and return an upload url (url is /v2/<name>/blobs/uploads/)
    """

    permission_classes = []
    allowed_methods = (
        "POST",
        "PUT",
        "PATCH",
    )

    @never_cache
    @method_decorator(
        ratelimit(
            key="ip",
            rate=settings.VIEW_RATE_LIMIT,
            method="PUT",
            block=settings.VIEW_RATE_LIMIT_BLOCK,
        )
    )
    def put(self, request, *args, **kwargs):
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
        session_id = kwargs.get("session_id")
        digest = request.GET.get("digest")
        content_length = int(request.META.get("CONTENT_LENGTH", 0))
        content_type = request.META.get("CONTENT_TYPE", settings.DEFAULT_CONTENT_TYPE)

        # Presence of content range distinguishes chunked upload from single PUT
        # A final PUT request may not have a content_range if no chunk to upload
        content_range = request.META.get("HTTP_CONTENT_RANGE")

        if not session_id or not digest or not content_type:
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
        blob = get_object_or_404(Blob, id=blob_id, digest=version)

        # If allow_continue False, return response
        allow_continue, response, _ = is_authenticated(
            request, blob.repository, must_be_owner=True
        )
        if not allow_continue:
            return response

        if not content_range and request.body:

            # Now process the PUT request to the file! Provide the blob to update
            return storage.create_blob(
                blob=blob,
                body=request.body,
                digest=digest,
                content_type=content_type,
            )

        # Scenario 2: a PUT to end a chunked upload session, no final chunk
        elif not request.body:
            return storage.finish_blob(
                blob=blob,
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
        status_code = storage.write_chunk(
            blob=blob,
            content_start=content_start,
            content_end=content_end,
            body=request.body,
        )

        # If it's already existing, return Accepted header, otherwise alert created
        if status_code != 202:
            return Response(status=status_code)

        return storage.finish_blob(
            blob=blob,
            digest=digest,
        )

    @never_cache
    def patch(self, request, *args, **kwargs):
        """a patch request is done after a POST with content-length 0 to indicate
        a chunked upload request.
        """
        session_id = kwargs.get("session_id")
        content_length = int(request.META.get("CONTENT_LENGTH"))
        content_range = request.META.get("HTTP_CONTENT_RANGE")
        content_type = request.META.get("CONTENT_TYPE")

        if not session_id or not content_length or not content_type:
            return Response(status=400)

        # If a content range is not defined, assume start to end
        if not content_range:
            content_start = 0
            content_end = content_length - 1

        else:
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
        _, blob_id, version = session_id.split("/", 3)
        blob = get_object_or_404(Blob, id=blob_id, digest=version)
        allow_continue, response, _ = is_authenticated(
            request, blob.repository, must_be_owner=True
        )
        if not allow_continue:
            return response

        # Update the blob content_type TODO: There should be some check
        # to ensure that a next chunk content type is not different from that
        # already defined
        blob.content_type = content_type

        # Now process the PATCH request to upload the chunk
        return storage.upload_blob_chunk(
            blob=blob,
            body=request.body,
            content_start=content_start,
            content_end=content_end,
            content_length=content_length,
        )

    @never_cache
    @method_decorator(
        ratelimit(
            key="ip",
            rate=settings.VIEW_RATE_LIMIT,
            method="POST",
            block=settings.VIEW_RATE_LIMIT_BLOCK,
        )
    )
    def post(self, request, *args, **kwargs):
        """POST /v2/<name>/blobs/uploads/"""

        # the name is only used to validate the user has permission to upload
        name = kwargs.get("name")

        # Look if we want to mount (get) a blob from another repository
        mount = request.GET.get("mount")
        from_repo = request.GET.get("from")

        # Validate user having a token, no repository required
        allow_continue, response, user = is_authenticated(
            request, name, repository_exists=False
        )
        if not allow_continue:
            return response

        # For check media type and content length (if needed)
        content_length = int(request.META.get("CONTENT_LENGTH", 0))
        content_type = request.META.get("CONTENT_TYPE", settings.DEFAULT_CONTENT_TYPE)

        # If no content length, tell the user it's required
        if content_length in [None, ""]:
            return Response(status=411)

        # Get or create the requested repository
        repository, created = Repository.objects.get_or_create(name=name)

        # If created, add user to owners
        if created:
            repository.owners.add(user)
            repository.save()

        # Otherwise, must be an owner
        else:
            allow_continue, response, _ = is_authenticated(
                request, repository, must_be_owner=True
            )
            if not allow_continue:
                return response

        # Case 1: POST provided with digest == single monolithic upload
        # /v2/<name>/blobs/uploads/?digest=<digest>
        if "digest" in request.GET:

            # Unsupported media type, only needed for digest
            if content_type not in settings.CONTENT_TYPES:
                return Response(status=415)

            digest = request.GET["digest"]

            # Confirm that content length (body) == header value, otherwise bad request
            if len(request.body) != content_length:
                return Response(status=400)

            # The storage.create_blob handles creation of blob with body (no second request required)
            # We only pass the name to return it with the blob's download url, there is no association
            return storage.create_blob(
                body=request.body,
                digest=digest,
                content_type=content_type,
                repository=repository,
            )

        # Case 2: Mount a blob from a different repository
        # /v2/<name>/blobs/uploads/?mount=<digest>&from=<other_name>
        elif mount and from_repo:

            # Get the existing repository
            from_repository = get_object_or_404(Repository, name=from_repo)

            # Mount is the digest of the blob we need. We use the same datafile
            try:
                blob = Blob.objects.get(digest=mount, repository=from_repository)
            except Blob.DoesNotExist:
                # Cross-mounting of nonexistent blob should yield session id
                return storage.create_blob_request(repository)

            # Unset the pk and id, and add a new repository
            blob.pk = None
            blob.id = None
            blob.repository = repository
            blob.save()

            # Successful mount MUST be 201 Created, and MUST contain Location: <blob-location>
            return Response(status=201, headers={"Location": blob.get_download_url()})

        # Case 3; Content type length 0 indicates chunked upload
        elif content_length != 0:
            return storage.create_blob_request(repository)

        # Case 3: POST without digest == single monolithic with POST then PUT
        # returns a session location to upload to with PUT
        return storage.create_blob_request(repository)
