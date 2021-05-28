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

from django.core.files.storage import FileSystemStorage
from django_oci import settings
from django.urls import reverse
from django.db import models
from django.contrib.auth.models import User
from django.middleware import cache

import hashlib
import json
import os
import re


PRIVACY_CHOICES = (
    (False, "Public (The collection will be accessible by anyone)"),
    (True, "Private (The collection will be not listed.)"),
)


def get_privacy_default():
    return settings.PRIVATE_ONLY


class OverwriteStorage(FileSystemStorage):
    def get_available_name(self, name, **kwargs):
        """Define a new filesystem storage so that it's okay to overwrite an
        existing filename.
        """
        if self.exists(name):
            os.remove(name)
        return name

    def get_valid_name(self, name, **kwargs):
        """The default function will replace the : in the filename (removing it)
        but we want to allow it.
        """
        name = str(name).strip().replace(" ", "_")
        return re.sub(r"(?u)[^-\w.:]", "", name)


def calculate_digest(body):
    """Calculate the sha256 sum for some body (bytes)"""
    hasher = hashlib.sha256()
    hasher.update(body)
    return hasher.hexdigest()


def get_upload_folder(instance, filename):
    """a helper function to upload a blob to local storage"""
    repository_name = instance.repository.name
    blobs_home = os.path.join(settings.MEDIA_ROOT, "blobs", repository_name)
    if not os.path.exists(blobs_home):
        os.makedirs(blobs_home)
    filename = os.path.join(blobs_home, filename)
    return filename


def get_image_by_tag(name, reference, tag, create=False, body=None):
    """given the name of a repository and a reference, look up the image
    based on the reference. By default we use the reference to look for
    a tag or digest. A return of None indicates that the image is not found,
    and the view should deal with this (e.g., create the image) or raise
    Http404.

    Parameters
    ==========
    name (str): the name of the repository to lookup
    reference (str): an image version string
    tag (str): a tag that doesn't match as a version string
    create (bool): if does not exist, create the image (new manifest push)
    body (bytes): if we need to create, we must have a digest from the body
    """
    # Ensure the repository exists
    try:
        repository = Repository.objects.get(name=name)
    except Repository.DoesNotExist:
        return None

    # reference can be a tag (more likely) or digest
    image = None
    if tag:
        try:
            image = repository.image_set.get(tag__name=tag)
        except Image.DoesNotExist:
            pass

    elif reference:
        try:
            image = repository.image_set.get(version=reference)
        except Image.DoesNotExist:
            pass

    if not image and create:
        if not reference and body:
            reference = "sha256:%s" % calculate_digest(body)
        image, _ = Image.objects.get_or_create(
            repository=repository, version=reference, manifest=body
        )
        if tag:
            tag, _ = Tag.objects.get_or_create(image=image, name=tag)
            tag.image = image
            tag.save()

        # This saves annotations and layer (blob) associations
        image.update_manifest(body)

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
        User,
        blank=True,
        default=None,
        related_name="container_collection_owners",
        related_query_name="owners",
    )
    contributors = models.ManyToManyField(
        User,
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

    def has_view_permission(self, user):
        return user in self.owners.all() or user in self.contributors.all()

    def get_absolute_url(self):
        return reverse("repository_details", args=[str(self.id)])

    def __str__(self):
        return self.get_uri()

    def __unicode__(self):
        return self.get_uri()

    def get_uri(self):
        return self.name

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
    datafile = models.FileField(
        upload_to=get_upload_folder, max_length=255, storage=OverwriteStorage()
    )
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

        # Expires in default 10 seconds
        filecache.set(self.session_id, 1, timeout=settings.SESSION_EXPIRES_SECONDS)
        return reverse("django_oci:blob_upload", kwargs={"session_id": self.session_id})

    @property
    def session_id(self):
        return "put/%s/%s" % (self.id, self.digest)

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
    manifest = models.BinaryField(null=False, blank=False, default=b"{}")

    # The version (digest) of the manifest
    version = models.CharField(max_length=250, null=True, blank=True)

    # Manifest functions to get, save, and return download url
    def get_manifest(self):
        return self.manifest

    def add_blob(self, digest):
        """A helper function to lookup and add a blob to an image. If the blob
        is already added, no harm done.
        """
        if digest:
            try:
                blob = Blob.objects.get(digest=digest, repository=self.repository)
                self.blobs.add(blob)
            except Blob.DoesNotExist:
                pass

    def remove_blob(self, digest):
        """We can only remove a blob if it is no longer linked to any images
        for the repository. This should be called after new blobs are parsed
        and added via the manifest.
        """
        if digest:
            try:
                blob = Blob.objects.get(digest=digest, repository=self.repository)
                if blob.image_set.count() == 0:
                    blob.delete()
            except Blob.DoesNotExist:
                pass

    def update_blob_links(self, manifest):
        # Keep a list of blobs that we will remove
        current_blobs = set()

        # The configuration blob, and then all blob layers
        config_digest = manifest.get("config", {}).get("digest")
        current_blobs.add(config_digest)
        for layer in manifest.get("layers", []):
            current_blobs.add(layer.get("digest"))

        # Remove unlinked blobs
        unlinked_blobs = [x for x in self.blobs.all() if x.digest not in current_blobs]

        # Add all current blobs not already present, remove unlinked
        [self.add_blob(digest) for digest in current_blobs]
        [self.remove_blob(x) for x in unlinked_blobs]

    def update_annotations(self, manifest):
        # Just delete all previous annotations
        self.annotation_set.all().delete()
        for key, value in manifest.get("annotations", {}).items():
            annotation, created = Annotation.objects.get_or_create(key=key, image=self)
            annotation.value = value
            annotation.save()

    def update_manifest(self, manifest):
        """Loading a manifest (after save) means creating an association between blobs and
        annotations
        """
        # Load a derivation to get blob links and annotations
        if not isinstance(manifest, str):
            manifest = manifest.decode("utf-8")
        if not isinstance(manifest, dict):
            manifest = json.loads(manifest)
        self.update_blob_links(manifest)
        self.update_annotations(manifest)
        self.save()

    def get_manifest_url(self):
        if self.version:
            return reverse(
                "django_oci:image_manifest",
                kwargs={"name": self.repository.name, "reference": self.version},
            )
        return reverse(
            "django_oci:image_manifest",
            kwargs={"name": self.repository.name, "tag": self.tag_set.first().name},
        )

    # A container only gets a version when fit's frozen, otherwise known by tag
    def get_uri(self):
        return self.repository.name

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

    def __str__(self):
        return "<tag:%s>" % self.name


class Annotation(models.Model):
    """An annotation is a key/value pair to describe an image.
    We will want to parse these from an image manifest (eventually)
    """

    key = models.CharField(max_length=250, null=False, blank=False)
    value = models.CharField(max_length=250, null=False, blank=False)
    image = models.ForeignKey(Image, on_delete=models.CASCADE)

    def __str__(self):
        return "%s:%s" % (self.key, self.value)

    def __unicode__(self):
        return "%s:%s" % (self.key, self.value)

    def get_label(self):
        return "annotation"

    class Meta:
        app_label = "django_oci"
        unique_together = (("key", "image"),)
