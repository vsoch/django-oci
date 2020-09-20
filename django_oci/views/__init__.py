from .base import APIVersionCheck
from .blobs import BlobUpload, BlobDownload
from .image import ImageManifest, ImageTags
from .chunked import ChunkedUploadDemo, MyChunkedUploadView, MyChunkedUploadCompleteView

# Load storage on application init
from django_oci.storage import get_storage

storage = get_storage()
