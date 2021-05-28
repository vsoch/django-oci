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

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django_oci.settings import MEDIA_ROOT
from django.db import models
from datetime import timezone

import os
import hashlib


class ChunkedUpload(models.Model):
    """We can use an abstract class to interact with a chunked upload without
    saving anything to the database.
    """

    session_id = models.CharField(max_length=255)
    file = models.FileField(
        max_length=255, upload_to=os.path.join(MEDIA_ROOT, "sessions")
    )
    offset = models.BigIntegerField(default=0)

    @property
    def filename(self):
        return os.path.basename(self.session_id)

    @property
    def expires_on(self):
        return self.created_on + 10000

    @property
    def expired(self):
        return self.expires_on <= timezone.now()

    @property
    def sha256(self):
        if getattr(self, "_md5", None) is None:
            hasher = hashlib.sha256()
            for chunk in self.file.chunks():
                hasher.update(chunk)
            self._sha256 = hasher.hexdigest()
        return self._sha256

    def delete(self, delete_file=True, *args, **kwargs):
        if self.file:
            storage, path = self.file.storage, self.file.path
        super(ChunkedUpload, self).delete(*args, **kwargs)
        if self.file and delete_file:
            storage.delete(path)

    def __str__(self):
        return "<%s: session_id: %s - bytes: %s>" % (
            self.filename,
            self.session_id,
            self.offset,
        )

    def write_chunk(self, chunk, chunk_start):
        """Append a chunk to the file, or write the file if it doesn't exist yet.
        This is done to a temporary storage location in images/sessions until
        the blob is finalized.
        """
        self.file.close()

        # If it's the first chunk, we need to instantiate the file
        if chunk_start == 0:
            self.file.save(name=self.filename, content=ContentFile(""), save=False)

        # We should start writing at next index, not over a previously written one
        if self.file.size == 0 and chunk_start != 0:
            return 415

        # If a chunk is uploaded out of order, the registry MUST respond with a 416 Requested Range Not Satisfiable code.
        elif chunk_start != 0 and self.file.size != chunk_start:
            return 416

        # Write chunk (mode = append+binary)
        with open(self.file.path, mode="ab") as fd:
            fd.write(chunk)

        # Update the offset
        self.offset += len(chunk)
        self._sha256 = None  # Clear cached hash digest
        self.file.close()  # Flush
        return 202

    def get_uploaded_file(self):
        self.file.close()
        self.file.open(mode="rb")  # mode = read+binary
        return UploadedFile(file=self.file, name=self.filename, size=self.offset)
