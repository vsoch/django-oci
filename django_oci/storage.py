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

from django.http.response import Http404, HttpResponse
from django_oci import settings
from django.urls import reverse
from django_oci.models import Blob, Image, Repository
from django_oci.utils import parse_image_name
from rest_framework.response import Response

from io import BytesIO
import hashlib
import logging

logger = logging.getLogger(__name__)


def get_storage():
    """Return the correct storage handler based on the key obtained from
    settings
    """
    storage = settings.STORAGE_BACKEND
    lookup = {"filesystem": FileSystemStorage}
    if storage not in lookup:
        logger.warning(
            f"{storage} not supported as a storage backend, defaulting to filesystem."
        )
        storage = "filesystem"
    return lookup[storage]()


# Storage backends for django_oci
# each should have default set of functions for:
# monolithic upload
# chunked upload
# etc.


class StorageBase:
    """A storage base provides shared functions for a storage type"""

    def calculate_digest(self, body):
        """Calculate the sha256 sum for some body (bytes)"""
        hasher = hashlib.sha256()
        hasher.update(body)
        return hasher.hexdigest()


class FileSystemStorage(StorageBase):
    def create_blob_request(self, name):
        """A create blob request is intended to be done first with a name,
        and content type, and we do all steps of the creation
        except for the actual upload of the file, which is handled
        by a second PUT request to a session id.
        """
        # Generate blob upload session to return to the user
        version = "session-%s" % uuid.uuid4()
        blob = Blob.objects.create(version=version)
        blob.save()

        # Upon success, the response MUST have a code of 202 Accepted with a location header
        return Response(status=202, headers={"Location": blob.create_upload_session()})


    def finish_blob(
        self,
        blob,
        name,
        digest,
    ):
        """Finish a blob, meaning finalizing the digest and returning a download
        url relative to the name provided.
        """
        #TODO: in the case of a blob created from upload session, need to rename to be digest
        blob.digest = digest
        blob.save()

        # Location header must have <blob-location> being a pullable blob URL.
        return Response(status=201, headers={"Location": blob.get_download_url(name)})

    def create_blob(self, name, digest, body, content_type, blob=None):
        """Create an image blob from a monolithic post. We get the repository
        name along with the body for the blob and the digest.

        Parameters
        ==========
        name (str): the name of the repository eventually linked to
        body (bytes): the request body to write the container
        digest (str): the computed digest of the blob
        content_type (str): the blob content type
        blob (models.Blob): a blob object (if already created)
        """
        # the <digest> MUST match the blob's digest (how to calculate)
        calculated_digest = self.calculate_digest(body)
        if calculated_digest != digest:
            return Response(status=400)

        # If we don't have the blob object yet
        if not blob:
            blob, created = Blob.objects.get_or_create(digest=calculated_digest)

        # Update blob body if doesn't exist
        if not blob.datafile:
            datafile = SimpleUploadedFile(
                calculated_digest, body, content_type=content_type
            )
            blob.datafile = datafile

        # The digest is updated here if it was previously a session id
        blob.content_type = content_type
        blob.digest = digest
        blob.save()

        # If it's already existing, return Accepted header, otherwise alert created
        status_code = 202
        if created:
            status_code = 201

        # Location header must have <blob-location> being a pullable blob URL.
        # Image name is not associated with blob, but must be provided
        return Response(
            status=status_code, headers={"Location": blob.get_download_url(name)}
        )

    def upload_blob_chunk(
        self,
        blob,
        name,
        body,
        content_start,
        content_end,
        content_length,
    ):
        """Upload a chunk of a blob

        Parameters
        ==========
        blob (Blob): the blob to upload to
        body (bytes): the request body to write to the blob
        content_type (str): the blob content type
        content_start (int): the content starting index
        content_end (int): the content ending index
        content_length (int): the content length
        """
        status_code = blob.write_chunk(content_start=content_start, content_end=content_end, body=body)

        # If it's already existing, return Accepted header, otherwise alert created
        if status_code not in [201, 202]:
            return Response(status=status_code)

        # Generate an updated <location>
        return Response(
            status=status_code, headers={"Location": blob.get_download_url(name)}
        )


    def download_blob(self, name, digest):
        """Given a blob repository name and digest, return response to stream download.
        The repository name is associated to the blob via the image.
        """
        # TODO: might need to retrieve blob first and then check that the image is associated
        try:
            blob = Blob.objects.get(digest=digest, image__repository__name=name)
        except Blob.DoesNotExist:
            raise Http404

        blob_path = os.path.join(settings.MEDIA_ROOT, blob.datafile.name)
        if os.path.exists(blob_path):
            with open(file_path, "rb") as fh:
                response = HttpResponse(fh.read(), content_type=blob.content_type)
                response[
                    "Content-Disposition"
                ] = "inline; filename=" + os.path.basename(file_path)
                return response
