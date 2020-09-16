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

from django_oci import settings
from django.urls import reverse
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_delete

from django.middleware import cache
import uuid

import os
import uuid

PRIVACY_CHOICES = (
    (False, "Public (The collection will be accessible by anyone)"),
    (True, "Private (The collection will be not listed.)"),
)


def get_privacy_default():
    return settings.PRIVATE_ONLY


def get_upload_folder(instance, filename):
    """a helper function to upload to local storage"""
    repository_name = instance.image.repository.name.lower()

    # First get a collection
    try:
        repository = Repository.objects.get(name=repository_name)
    except Repository.DoesNotExist:
        return

    # Create collection root, if it doesn't exist
    image_home = os.path.join(settings.MEDIA_ROOT, repository_name)
    if not os.path.exists(image_home):
        os.makedirs(image_home)

    return os.path.join(image_home, filename)


class Repository(models.Model):

    name = models.CharField(
        max_length=500,  # name of repository, e.g., username/reponame
        unique=True,
        blank=False,
        null=False,
    )

    add_date = models.DateTimeField("date added", auto_now_add=True)
    modify_date = models.DateTimeField("date modified", auto_now=True)
    owners = models.ManyToManyField(
        settings.AUTHENTICATED_USER or User,
        blank=True,
        default=None,
        related_name="container_collection_owners",
        related_query_name="owners",
    )
    contributors = models.ManyToManyField(
        settings.AUTHENTICATED_USER or User,
        related_name="container_collection_contributors",
        related_query_name="contributor",
        blank=True,
        help_text="users with edit permission to the collection",
        verbose_name="Contributors",
    )

    # By default, collections are public
    private = models.BooleanField(
        choices=PRIVACY_CHOICES,
        default=get_privacy_default,
        verbose_name="Accessibility",
    )

    def get_absolute_url(self):
        return reverse("repository_details", args=[str(self.id)])

    def __str__(self):
        return self.get_uri()

    def __unicode__(self):
        return self.get_uri()

    def get_uri(self):
        return "%s:%s" % (self.name, self.image_set.count())

    def get_label(self):
        return "repository"

    class Meta:
        app_label = "django_oci"


class Image(models.Model):
    """A container image holds a particular version of a container for
    a registry.
    """

    add_date = models.DateTimeField("date container added", auto_now=True)

    # When a repository is deleted, so are the containers
    repository = models.ForeignKey(
        Repository,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )

    tag = models.CharField(max_length=250, null=False, blank=False, default="latest")

    # TODO: how do we define the version for this? digest of manifest?
    version = models.CharField(max_length=250, null=True, blank=True)

    # A container only gets a version when it's frozen, otherwise known by tag
    def get_uri(self):
        return "%s:%s" % (self.repository.name, self.tag)

    def create_upload_session(self):
        """A function to create an upload session for a particular image"""
        # Get the django oci upload cache, and generate an expiring session upload id
        filecache = cache.caches["django_oci_upload"]
        session_id = "put/%s/%s/%s" % (self.repository.name, self.id, uuid.uuid4())

        # Expires in default 10 seconds
        filecache.set(session_id, 1, timeout=settings.SESSION_EXPIRES_SECONDS)
        return reverse(
            "django_oci:image_blob_upload", kwargs={"session_id": session_id}
        )

    # Return an image file path
    def get_image_path(self):
        if self.image not in [None, ""]:
            return self.image.datafile.path
        return None

    def get_download_url(self):
        if self.image not in [None, ""]:
            return self.image.datafile.file
        return None

    def get_label(self):
        return "image"

    def __str__(self):
        return self.get_uri()

    def __unicode__(self):
        return self.get_uri()

    class Meta:
        app_label = "django_oci"
        unique_together = (
            (
                "repository",
                "tag",
            ),
        )


class Blob(models.Model):
    """a blob, which can be a binary or archive to be extracted."""

    add_date = models.DateTimeField("date added", auto_now_add=True)
    modify_date = models.DateTimeField("date modified", auto_now=True)
    content_type = models.CharField(max_length=250, null=False)
    digest = models.CharField(max_length=250, null=True, blank=True)
    image = models.ForeignKey(
        Image,
        related_name="blobs",
        related_query_name="blobs",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    datafile = models.FileField(upload_to=get_upload_folder, max_length=255)
    remotefile = models.CharField(max_length=500, null=True, blank=True)

    def get_label(self):
        return "blob"

    def get_download_url(self):
        if self.remotefile is not None:
            return self.remotefile
        return settings.DOMAIN_URL.strip("/") + reverse(
            "django_oci:image_blob_download",
            kwargs={"name": self.image.repository.name, "digest": self.digest},
        )

    def get_abspath(self):
        return os.path.join(settings.MEDIA_ROOT, self.datafile.name)

    class Meta:
        app_label = "django_oci"


class Annotation(models.Model):
    """An annotation is a key/value pair to describe an image"""

    key = models.CharField(max_length=250, null=False, blank=False)
    value = models.CharField(max_length=250, null=False, blank=False)
    images = models.ManyToManyField(Image, blank=False, related_name="annotations")

    def __str__(self):
        return "%s:%s" % (self.key, self.value)

    def __unicode__(self):
        return "%s:%s" % (self.key, self.value)

    def get_label(self):
        return "annotation"

    class Meta:
        app_label = "django_oci"
        unique_together = (("key", "value"),)


def delete_blobs(sender, instance, **kwargs):
    for image in instance.image_set.all():
        if hasattr(image, "datafile"):
            count = Image.objects.filter(image__datafile=image.datafile).count()
            if count == 0:
                print("Deleting %s, no longer used." % image.datafile)
                image.datafile.delete()


from chunked_upload.models import ChunkedUpload

# 'ChunkedUpload' class provides almost everything for you.
# if you need to tweak it little further, create a model class
# by inheriting "chunked_upload.models.AbstractChunkedUpload" class
MyChunkedUpload = ChunkedUpload

post_delete.connect(delete_blobs, sender=Image)
