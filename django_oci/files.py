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

from django.core.files.uploadedfile import UploadedFile

from io import BytesIO


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
