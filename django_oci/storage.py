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

    def __init__(self, name, file=None, content=None, content_type='application/octet-stream'):
        """TODO: we need to be able to init this and have option 1: write all bytesio to file (if content_range starts with 0)
           OR if not, to just hand the dataflie.file to some field here to manage
        """
        # If not given a file, this is the first call (and we create an in memory bytes)
        if not file:
            file = BytesIO(content or b'')
            content_length = 0 if not content else len(content)

        # Otherwise, we already have a file object to read
        else:
            content_length = file.size

        super().__init__(file, name, content_type, content_length, None, None)


    def update_chunk(self, body, content_range):
        """Given some body, a start, and end (range), write the chunk to the fle
        """
        start = content_range.split() # SOMETHING
        end = ...
        # TODO stopped here - need to look at what data looks like to write function
        # Seek to spot in file
        self.file.seek(start)
        # TODO need to lookup how to seek and write to spot

        # TODO ceck that curent file length is the correct start, otherwise return custom
        # error
        # If a chunk is uploaded out of order, the registry MUST respond with a 416 Requested Range Not Satisfiable code.
        return 416

        return 202

def get_storage():
    """Return the correct storage handler based on the key obtained from
       settings
    """
    storage = settings.STORAGE_BACKEND
    lookup = {"filesystem": FileSystemStorage}
    if storage not in lookup:
        logger.warning(f"{storage} not supported as a storage backend, defaulting to filesystem.")         
        storage = "filesystem"
    return lookup[storage]()

def get_upload_session(name):
    """return the image object for an upload session"""
    ids = parse_image_name(name)
    tag = ids.get('tag', 'latest')
    collection = ids.get('url')

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
    """A storage base provides shared functions for a storage type
    """  
  
    def calculate_digest(self, body):
        """Calculate the sha256 sum for some body (bytes)
        """
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
        tag = ids.get('tag', 'latest')
        collection = ids.get('url')

        # Here we get the repository based on the name (get or create)
        # TODO: will need to add owner
        repository, _ = Repository.objects.get_or_create(name=collection)

        # Get the image associated with the tag
        image, _ = Image.objects.get_or_create(repository=repository, tag=tag)

        # Create the blob, and associate with image
        blob, created = Blob.objects.get_or_create(digest=calculated_digest, content_type=content_type, image=image)

        # Update blob body
        datafile = SimpleUploadedFile(calculated_digest, body, content_type=content_type)
        blob.datafile = datafile
        blob.save()

        # If it's already existing, return Accepted header, otherwise alert created        
        status_code = 202
        if created:
            status_code = 201        

        # Location header must have <blob-location> being a pullable blob URL.
        return Response(status=status_code, headers={"Location": blob.get_download_url()})


    def upload_blob_chunk(self, repository, image, body, content_type, content_range, content_length, session_id):
        """Upload a chunk of a blob

           Parameters
           ==========
           repository (Repository): the repository
           image (Image): the image to upload to
           body (bytes): the request body to write the container
           content_type (str): the blob content type
           content_range (str): the content range to upload to
           content_length (int): the content length
        """       
        return Response(status=200)

        # Create the blob, and associate with image - we use the session_id as the digest until completion
        blob, created = Blob.objects.get_or_create(digest=session_id, content_type=content_type, image=image)

        # If we don't yet have a blob.datafile, create a new one, assert that upload_range starts at 0
        # TODO look at example of what this looks like
        if not blob.datafile:
            # TODO assert starting at 0
            datafile = ChunkedFile(name=session_id, content=body, content_type=content_type)

        # Uploading another chunk for existing file
        else:
            datafile = ChunkedFile(name=session_id, file=blob.datafile.file, content_type=blob.content_type)

        # Update the chunk
        status_code = datafile.update_chunk(body, content_range)
        
        blob.datafile = datafile
        blob.save()

        # If it's already existing, return Accepted header, otherwise alert created        

        # Location header must have <blob-location> being a pullable blob URL.
        return Response(status=status_code, headers={"Location": blob.get_download_url()})



def create(request):
#    print request.POST
    filename = request.POST['name'] 
    f = open(filename, "w")
    structure = Structure(name=request.POST['name'], file=File(f))
    structure.save()
    return redirect('/structures')


# Each successful chunk upload MUST have a 202 Accepted response code, and MUST have the following header:

#Location <location>

# TODO should we remove and generate a new session? YES
#Each consecutive chunk upload SHOULD use the <location> provided in the response to the previous chunk upload.

#Chunks MUST be uploaded in order, with the first byte of a chunk being the last chunk's <end-of-range> plus one. If a chunk is uploaded out of order, the registry MUST respond with a 416 Requested Range Not Satisfiable code.

#The final chunk MAY be uploaded using a PATCH request or it MAY be uploaded in the closing PUT request. Regardless of how the final chunk is uploaded, the session MUST be closed with a PUT request.

    def download_blob(self, name, digest):
        """Given a blob repository name and digest, return response to stream download.
           The repository name is associated to the blob via the image.
        """
        ids = parse_image_name(name)
        try:
            blob = Blob.objects.get(digest=digest, image__repository__name=ids['url'])
        except Blob.DoesNotExist:
            raise Http404

        blob_path = os.path.join(settings.MEDIA_ROOT, blob.datafile.name)
        if os.path.exists(blob_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type=blob.content_type)
                response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
                return response
