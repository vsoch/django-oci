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
from django.urls import reverse
from django_oci import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django_oci.files import ChunkedUpload
from django_oci.models import Blob
from rest_framework.response import Response

import hashlib
import logging
import shutil
import uuid
import os

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
    def create_blob_request(self, repository):
        """A create blob request is intended to be done first with a name,
        and content type, and we do all steps of the creation
        except for the actual upload of the file, which is handled
        by a second PUT request to a session id.
        """
        # Generate blob upload session to return to the user
        version = "session-%s" % uuid.uuid4()
        blob = Blob.objects.create(digest=version, repository=repository)
        blob.save()

        # Upon success, the response MUST have a code of 202 Accepted with a location header
        return Response(status=202, headers={"Location": blob.create_upload_session()})

    def finish_blob(
        self,
        blob,
        digest,
    ):
        """Finish a blob, meaning finalizing the digest and returning a download
        url relative to the name provided.
        """

        # In the case of a blob created from upload session, need to rename to be digest
        if blob.datafile.name != digest:
            final_path = os.path.join(
                settings.MEDIA_ROOT, "blobs", blob.repository.name, digest
            )
            if not os.path.exists(final_path):
                dirname = os.path.dirname(final_path)
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                shutil.move(blob.datafile.path, final_path)
            else:
                os.remove(blob.datafile.name)
            blob.datafile.name = digest

        # Delete the blob if it already existed
        try:
            existing_blob = Blob.objects.get(repository=blob.repository, digest=digest)
            existing_blob.delete()
        except:
            pass

        blob.digest = digest
        blob.save()

        # Location header must have <blob-location> being a pullable blob URL.
        return Response(status=201, headers={"Location": blob.get_download_url()})

    def create_blob(self, digest, body, content_type, blob=None, repository=None):
        """Create an image blob from a monolithic post. We get the repository
        name along with the body for the blob and the digest.

        Parameters
        ==========
        body (bytes): the request body to write the container
        digest (str): the computed digest of the blob
        content_type (str): the blob content type
        blob (models.Blob): a blob object (if already created)
        """
        # the <digest> MUST match the blob's digest (how to calculate)
        calculated_digest = self.calculate_digest(body)

        # If there is an algorithm prefix, add it
        if ":" in digest:
            calculated_digest = "%s:%s" % (digest.split(":")[0], calculated_digest)

        if calculated_digest != digest:
            return Response(status=400)

        # If we don't have the blob object yet
        created = False
        if not blob:
            blob, created = Blob.objects.get_or_create(
                digest=calculated_digest, repository=repository
            )

        # Delete the blob if it already existed
        try:
            existing_blob = Blob.objects.get(repository=blob.repository, digest=digest)
            existing_blob.delete()
        except:
            pass

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
        # NOTE: this is set to 201 currently because the conformance test only allows that
        # status_code = 202
        # if created:
        status_code = 201

        # Location header must have <blob-location> being a pullable blob URL.
        return Response(
            status=status_code, headers={"Location": blob.get_download_url()}
        )

    def upload_blob_chunk(
        self,
        blob,
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
        status_code = self.write_chunk(
            blob=blob, content_start=content_start, content_end=content_end, body=body
        )

        # If it's already existing, return Accepted header, otherwise alert created
        if status_code not in [201, 202]:
            return Response(status=status_code)

        # Generate the same upload <location>
        location = reverse(
            "django_oci:blob_upload", kwargs={"session_id": blob.session_id}
        )
        return Response(status=status_code, headers={"Location": location})

    def write_chunk(self, blob, content_start, content_end, body):
        """Write a chunk to a blob. During a chunked upload, the digest corresponds
        to the session_id, and is saved temporarily. It's named on upload finish.
        """
        # Ensure the size is correct (we add 1 to include the start index)
        if len(body) != content_end - content_start + 1:
            return 416

        # If we don't yet have a blob.datafile, create a new one, assert that upload_range starts at 0
        if not blob.datafile:

            # The first request must start at 0
            if content_start != 0:
                return 416

            # Create an empty data file
            datafile = ChunkedUpload(session_id=blob.digest)

        # Uploading another chunk for existing file
        else:
            datafile = ChunkedUpload(session_id=blob.digest, file=blob.datafile.file)

        # Update the chunk, get back the status code
        status_code = datafile.write_chunk(body, content_start)
        blob.datafile.name = datafile.file.name
        blob.save()
        return status_code

    def blob_exists(self, name, digest):
        """Given a blob repository name and digest, return a 200 response
        with the digest of the uploaded blob in the header Docker-Content-Digest.
        """
        try:
            blob = Blob.objects.get(digest=digest, repository__name=name)
        except Blob.DoesNotExist:
            raise Http404
        headers = {"Docker-Content-Digest": blob.digest}
        return Response(status=200, headers=headers)

    def download_blob(self, name, digest):
        """Given a blob repository name and digest, return response to stream download.
        The repository name is associated to the blob via the image.
        """
        try:
            blob = Blob.objects.get(digest=digest, repository__name=name)
        except Blob.DoesNotExist:
            raise Http404

        if os.path.exists(blob.datafile.name):
            with open(blob.datafile.name, "rb") as fh:
                response = HttpResponse(fh.read(), content_type=blob.content_type)
                response[
                    "Content-Disposition"
                ] = "inline; filename=" + os.path.basename(blob.datafile.name)
                return response

        # If we get here, file doesn't exist
        raise Http404

    def delete_blob(self, name, digest):
        """Given a blob repository name and digest, delete and return success (202)."""
        try:
            blob = Blob.objects.get(digest=digest, repository__name=name)
        except Blob.DoesNotExist:
            raise Http404

        # Delete the blob, will eventually need to check permissions
        blob.delete()
        return Response(status=202)


# Load storage on application init
storage = get_storage()
