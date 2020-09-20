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

import json
import os
import uuid

PRIVACY_CHOICES = (
    (False, "Public (The collection will be accessible by anyone)"),
    (True, "Private (The collection will be not listed.)"),
)


def get_privacy_default():
    return settings.PRIVATE_ONLY


def get_upload_folder(instance, filename):
    """a helper function to upload a blob to local storage"""
    repository_name = instance.repository.name
    blobs_home = os.path.join(settings.MEDIA_ROOT, "blobs", repository_name)
    if not os.path.exists(blobs_home):
        os.makedirs(blobs_home)

    return os.path.join(blobs_home, filename)


def get_image_by_tag(name, reference):
    """given the name of a repository and a reference, look up the image
    based on the reference. By default we use the reference to look for
    a tag or digest. A return of None indicates that the image is not found,
    and the view should raise Http404

    Parameters
    ==========
    name (str): the name of the repository to lookup
    reference (str): an image tag or version
    """
    if not name or not reference:
        return None

    # Ensure the repository exists
    try:
        repository = Repository.objects.get(name=name)
    except Repository.DoesNotExist:
        return None

    # reference can be a tag (more likely) or digest
    try:
        image = repository.image_set.get(tag__name=reference)
    except Repository.DoesNotExist:

        # Allow lookup based on a version string
        try:
            image = repository.image_set.get(version=reference)
        except:
            return None

    return image


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


class Blob(models.Model):
    """a blob, which can be a binary or archive to be extracted."""

    add_date = models.DateTimeField("date added", auto_now_add=True)
    modify_date = models.DateTimeField("date modified", auto_now=True)
    content_type = models.CharField(max_length=250, null=False)
    digest = models.CharField(max_length=250, null=True, blank=True)
    datafile = models.FileField(upload_to=get_upload_folder, max_length=255)
    remotefile = models.CharField(max_length=500, null=True, blank=True)

    # When a repository is deleted, so are the blobs
    repository = models.ForeignKey(
        Repository,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )

    def get_label(self):
        return "blob"

    def get_download_url(self):
        """Blobs are loosely associated with repositories."""
        if self.remotefile is not None:
            return self.remotefile
        return settings.DOMAIN_URL.strip("/") + reverse(
            "django_oci:blob_download",
            kwargs={"digest": self.digest, "name": self.repository.name},
        )

    def create_upload_session(self):
        """A function to create an upload session for a particular blob.
        The version variable will be set with a session id.
        """
        # Get the django oci upload cache, and generate an expiring session upload id
        filecache = cache.caches["django_oci_upload"]
        session_id = "put/%s/%s" % (self.id, self.digest)

        # Expires in default 10 seconds
        filecache.set(session_id, 1, timeout=settings.SESSION_EXPIRES_SECONDS)
        return reverse("django_oci:blob_upload", kwargs={"session_id": session_id})

    def get_abspath(self):
        return os.path.join(settings.MEDIA_ROOT, self.datafile.name)

    class Meta:
        app_label = "django_oci"
        unique_together = (
            (
                "repository",
                "digest",
            ),
        )


class Image(models.Model):
    """An image (manifest) holds a set of layers (blobs) for a repository.
    Blobs can be shared between manifests, and are deleted if they are
    no longer referenced.
    """

    add_date = models.DateTimeField("date manifest added", auto_now=True)

    # When a repository is deleted, so are the manifests
    repository = models.ForeignKey(
        Repository,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )

    # Blobs are added at the creation of the manifest (can be shared based on hash)
    blobs = models.ManyToManyField(Blob)

    # The text of the manifest (added at the end)
    manifest = models.TextField(null=False, blank=False, default="{}")

    # The version (digest) of the manifest
    version = models.CharField(max_length=250, null=True, blank=True)

    # Manifest functions to get, save, and return download url
    def get_manifest(self):
        return json.loads(self.text)

    def save_manifest(self, manifest):
        self.manifest = json.dumps(manifest)
        self.save()

    def get_download_url(self):
        return reverse(
            "django_oci:image_manifest",
            kwargs={"name": self.repository.name, "reference": self.tag.name},
        )

    # A container only gets a version when fit's frozen, otherwise known by tag
    def get_uri(self):
        return "%s:%s" % (self.repository.name, self.tag)

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
                "version",
            ),
        )


class Tag(models.Model):
    """A tag is a reference for one or more manifests"""

    name = models.CharField(max_length=250, null=False, blank=False)
    image = models.ForeignKey(
        Image,
        null=False,
        blank=False,
        # When a manifest is deleted, any associated tags are too
        on_delete=models.CASCADE,
    )


class Annotation(models.Model):
    """An annotation is a key/value pair to describe an image.
    We will want to parse these from an image manifest (eventually)
    """

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


# def delete_blobs(sender, instance, **kwargs):
#    for image in instance.image_set.all():
#        if hasattr(image, "datafile"):
#            count = Image.objects.filter(image__datafile=image.datafile).count()
#            if count == 0:
#                print("Deleting %s, no longer used." % image.datafile)
#                image.datafile.delete()


# post_delete.connect(delete_blobs, sender=Image)
