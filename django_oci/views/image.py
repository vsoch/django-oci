'''

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

'''

from rest_framework.views import APIView
from rest_framework.response import Response
from django.http.response import Http404, HttpResponse
from django_oci.models import Repository, Image
from django_oci import settings
from django.middleware import cache

from opencontainers.image.v1.manifest import Manifest 
from django_oci.storage import get_storage

import os


#from rest_framework import generics, serializers, viewsets, status
#from rest_framework.exceptions import PermissionDenied, NotFound
#from ratelimit.mixins import RatelimitMixin

# Load storage on application init
storage = get_storage()


class ImageBlobDownload(APIView):
    """Given a GET request for a blob, stream the blob.
    """
    permission_classes = []
    allowed_methods = ('GET',)

    def get(self, request, *args, **kwargs):
        """POST /v2/<name>/blobs/download/<digest>"""

        name = kwargs.get("name")
        digest = kwargs.get("digest")
        return storage.download_blob(name, digest)


class ImageBlobUpload(APIView):
    """An image push will receive a request to push, authenticate the user,
       and return an upload url (url is /v2/<name>/blobs/uploads/)
    """
    permission_classes = []
    allowed_methods = ('POST', 'PUT', 'PATCH')

    def put(self, request, *args, **kwrags):
        """A put request can come after a POST request, and must include a session_id
           The session id is created via the file system cache, and each one includes
           the request type, image id (associated with a tag), repository, and
           a randomly generated uuid. The upload will not continue if any required
           metadata is missing or the identifier is already expired.
        """
        session_id = kwargs.get("session_id")
        digest = request.GET.get('digest')
        content_length = int(request.META.get("CONTENT_LENGTH"))
        content_type = request.META.get("CONTENT_TYPE")
        if not session_id or not digest or not content_length or not content_type:
            return Response(status=400)

        # Confirm that content length (body) == header value, otherwise bad request
        if len(request.body) != content_length:
            return Response(status=400) 

        # Get the session id, if it has not expired
        filecache = cache.caches['django_oci_upload']
        if not filecache.get(session_id):
            return Response(status=400)

        # Ensure it cannot be used again
        filecache.set(session_id, None, timeout=0)

        # Break apart into repository name, image id, and uuid
        _, collection, image_id, _ = session_id.split('/')
        try:
            repository = Repository.objects.get(name=collection)
            image = Image.objects.get(id=image_id)
        except (Repository.DoesNotExist, Image.DoesNotExist):  
            return Response(status=404)        

        # Now process the PUT request to the file!
        return storage.create_blob(name=repository.name, body=request.body, digest=digest, content_type=content_type)


    def patch(self, request, *args, **kwargs):
        """a patch request is done after a POST with content-length 0 to indicate
           a chunked upload request.
           POST /v2/<name>/blobs/uploads/
        """
        session_id = kwargs.get("session_id")
        content_length = int(request.META.get("CONTENT_LENGTH"))
        content_range = int(request.META.get("CONTENT_RANGE"))
        content_type = request.META.get("CONTENT_TYPE")

        if not session_id or not content_range or not content_length or not content_type:
            return Response(status=400)

        # Ensure range matches regular expression
        if not re.search("^[0-9]+-[0-9]+$", content_range):
            return Response(status=400)

        # Confirm that content length (body) == header value, otherwise bad request
        if len(request.body) != content_length:
            return Response(status=400) 

        # Get the session id, if it has not expired, but don't close it
        filecache = cache.caches['django_oci_upload']
        if not filecache.get(session_id):
            return Response(status=400)

        # Break apart into repository name, image id, and uuid
        _, collection, image_id, _ = session_id.split('/')
        try:
            repository = Repository.objects.get(name=collection)
            image = Image.objects.get(id=image_id)
        except (Repository.DoesNotExist, Image.DoesNotExist):  
            return Response(status=404)        

        # Now process the PATCH request to upload the chunk
        return storage.upload_blob_chunk(repository=repository, image=image, session_id=session_id, body=request.body, content_type=content_type, content_range=content_range, content_length=content_length)

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
            digest = request.GET['digest']

            # Confirm that content length (body) == header value, otherwise bad request
            if len(request.body) != content_length:
                return Response(status=400) 

            # The storage.create_blob handles creation of blob with body (no second request required)
            return storage.create_blob(name=name, body=request.body, digest=digest, content_type=content_type)

        # Case 2; Content type length 0 indicates chunked upload
        elif content_length != 0:
            return storage.create_blob_request(name=name)

        # Case 3: POST without digest == single monolithic with POST then PUT
        # returns a session location to upload to with PUT
        return storage.create_blob_request(name=name)
        

class ImageManifest(APIView):
    """GET an image manifest, the starting operation to pull a container image.
    """
    permission_classes = []
    allowed_methods = ('GET',)

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

        # Create and validate a manifest
        manifest = Manifest()
        manifest.load()


# TODO have this created by opencontainers python
#{
#   "annotations": {
#      "com.example.key1": "value1",
#      "com.example.key2": "value2"
#   },
#   "config": {
#      "digest": "sha256:6f4e69a5ff18d92e7315e3ee31c62165ebf25bfa05cad05c0d09d8f412dae401",
#      "mediaType": "application/vnd.oci.image.config.v1+json",
#      "size": 452
#   },
#   "layers": [
#      {
#         "digest": "sha256:6f4e69a5ff18d92e7315e3ee31c62165ebf25bfa05cad05c0d09d8f412dae401",
#         "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
#         "size": 78343
#      }
#   ],
#   "schemaVersion": 2
#}
        headers = {"Docker-Distribution-API-Version": "registry/2.0"}
        return Response(manifest.to_dict())
