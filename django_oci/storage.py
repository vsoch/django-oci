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

from django.core.files.uploadedfile import SimpleUploadedFile, UploadedFile
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


class ChunkedFile(UploadedFile):
    """A ChunkedFile has additional methods to write chunks"""

    def __init__(
        self, name, file=None, content=None, content_type="application/octet-stream"
    ):
        # If not given a file, this is the first call (and we create an in memory bytes)
        if not file:
            file = BytesIO(content or b"")
            content_length = 0 if not content else len(content)

        # Otherwise, we already have a file object to read
        else:
            content_length = file.size

        super().__init__(file, name, content_type, content_length, None, None)

    def update_chunk(self, body, content_start, content_end):
        """Given some body, a start, and end (range), write the chunk to the fle"""

        # We should start writing at next index, not over a previously written one
        if self.file.size + 1 != content_start:

            # If a chunk is uploaded out of order, the registry MUST respond with a 416 Requested Range Not Satisfiable code.
            return 416

        # Write the new content to file
        with open(self.file.name, "wb") as fh:
            fh.seek(content_start)
            fh.write(body)

        # Update the content size
        self.file.size = self.file.size + (content_end - content_start)
        return 202


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


def get_upload_session(name):
    """return the image object for an upload session"""
    ids = parse_image_name(name)
    tag = ids.get("tag", "latest")
    collection = ids.get("url")

    # Here we get the repository based on the name (get or create)
    # TODO: will need to add owner
    repository, _ = Repository.objects.get_or_create(name=collection)

    # Get the image associated with the tag
    image, _ = Image.objects.get_or_create(repository=repository, tag=tag)
    return image


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
        # Generate image for an upload session to return to the user
        image = get_upload_session(name)

        # Upon success, the response MUST have a code of 202 Accepted with a location header
        return Response(status=202, headers={"Location": image.create_upload_session()})

    def finish_blob(
        self,
        image,
        digest,
        session_id=None,
        body=None,
        content_type=None,
        content_start=None,
        content_end=None,
    ):
        """Finish a blob. Optionally, a body and content_type and start/end
        bytes can be provided to write one more chunk.
        """
        # The user wants to write one more chunk
        if body and content_type and content_start and content_end and session_id:
            try:
                blob = self.write_blob_chunk(
                    image=image,
                    # We provide the session_id to use as a lookup
                    digest=session_id,
                    content_type=content_type,
                    content_start=content_start,
                    content_end=content_end,
                    body=body,
                )

            except ValueError:
                # Requested Range Not Satisfiable code (should be 0)
                return Response(status=416)

        # We just want to finalize the blob
        else:
            blob = Blob.objects.get(
                digest=session_id, content_type=content_type, image=image
            )

        # Blob's true digest is updated to not be session_id
        blob.digest = digest
        blob.save()

        # Location header must have <blob-location> being a pullable blob URL.
        return Response(status=201, headers={"Location": blob.get_download_url()})

    def create_blob(self, name, digest, body, content_type):
        """Create an image blob from a monolithic post. We get the repository
        name along with the body for the blob and the digest.

        Parameters
        ==========
        name (str): the name of the repository
        body (bytes): the request body to write the container
        digest (str): the computed digest of the blob
        content_type (str): the blob content type
        """
        # the <digest> MUST match the blob's digest (how to calculate)
        calculated_digest = self.calculate_digest(body)
        if calculated_digest != digest:
            return Response(status=400)

        # Parse image name to get tag, etc.
        ids = parse_image_name(name)
        tag = ids.get("tag", "latest")
        collection = ids.get("url")

        # Here we get the repository based on the name (get or create)
        # TODO: will need to add owner
        repository, _ = Repository.objects.get_or_create(name=collection)

        # Get the image associated with the tag
        image, _ = Image.objects.get_or_create(repository=repository, tag=tag)

        # Create the blob, and associate with image
        blob, created = Blob.objects.get_or_create(
            digest=calculated_digest, content_type=content_type, image=image
        )

        # Update blob body
        datafile = SimpleUploadedFile(
            calculated_digest, body, content_type=content_type
        )
        blob.datafile = datafile
        blob.save()

        # If it's already existing, return Accepted header, otherwise alert created
        status_code = 202
        if created:
            status_code = 201

        # Location header must have <blob-location> being a pullable blob URL.
        return Response(
            status=status_code, headers={"Location": blob.get_download_url()}
        )

    def upload_blob_chunk(
        self,
        repository,
        image,
        body,
        content_type,
        content_start,
        content_end,
        content_length,
        session_id,
    ):
        """Upload a chunk of a blob

        Parameters
        ==========
        repository (Repository): the repository
        image (Image): the image to upload to
        body (bytes): the request body to write the container
        content_type (str): the blob content type
        content_start (int): the content starting index
        content_end (int): the content ending index
        content_length (int): the content length
        """
        try:
            blob = self.write_blob_chunk(
                image=image,
                digest=session_id,
                content_type=content_type,
                content_start=content_start,
                content_end=content_end,
                body=body,
            )
        except ValueError:
            # Requested Range Not Satisfiable code (should be 0)
            return Response(status=416)

        # If it's already existing, return Accepted header, otherwise alert created
        if status_code != 202:
            return Response(status=status_code)

        # Generate an updated <location>
        return Response(
            status=status_code, headers={"Location": blob.get_download_url()}
        )

    def write_blob_chunk(
        self, image, digest, content_type, content_start, content_end, body
    ):
        """Write a chunk to a blob. During a chunked upload, the digest corresponds
        to the session_id
        """
        # Create the blob, and associate with image - we use the session_id as the digest until completion
        blob, created = Blob.objects.get_or_create(
            digest=digest, content_type=content_type, image=image
        )

        # If we don't yet have a blob.datafile, create a new one, assert that upload_range starts at 0
        if not blob.datafile:

            # The first request must start at 0
            if content_start != 0:
                raise ValueError(
                    "The first request for a chunked upload must start at 0."
                )

            datafile = ChunkedFile(name=digest, content=body, content_type=content_type)

        # Uploading another chunk for existing file
        else:
            datafile = ChunkedFile(
                name=digest, file=blob.datafile.file, content_type=blob.content_type
            )

        # Update the chunk, get back the status code
        status_code = datafile.update_chunk(body, content_start, content_end)

        blob.datafile = datafile
        blob.save()
        return blob

    def download_blob(self, name, digest):
        """Given a blob repository name and digest, return response to stream download.
        The repository name is associated to the blob via the image.
        """
        ids = parse_image_name(name)
        try:
            blob = Blob.objects.get(digest=digest, image__repository__name=ids["url"])
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
