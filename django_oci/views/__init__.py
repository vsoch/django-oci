# Load storage on application init
from django_oci.storage import get_storage

from .auth import GetAuthToken
from .base import APIVersionCheck
from .blobs import BlobDownload, BlobUpload
from .image import ImageManifest, ImageTags

storage = get_storage()
