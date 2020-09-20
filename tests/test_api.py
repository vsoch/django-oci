"""
test_django-oci api
-------------------

Tests for `django-oci` models module.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import TestCase
from django.test import Client

from time import sleep
import subprocess
import requests
import threading
import hashlib
import json
import os

here = os.path.abspath(os.path.dirname(__file__))


def calculate_digest(blob):
    """Given a blob (the body of a response) calculate the sha256 digest"""
    hasher = hashlib.sha256()
    hasher.update(blob)
    return hasher.hexdigest()


def read_in_chunks(image, chunk_size=1024):
    """Helper function to read file in chunks, with default size 1k."""
    while True:
        data = image.read(chunk_size)
        if not data:
            break
        yield data


def get_manifest(config_digest, layer_digest):
    """A dummy image manifest with a config and single image layer"""
    return json.dumps(
        {
            "schemaVersion": 2,
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "size": 7023,
                "digest": config_digest,
            },
            "layers": [
                {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                    "size": 32654,
                    "digest": layer_digest,
                }
            ],
            "annotations": {"com.example.key1": "peas", "com.example.key2": "carrots"},
        }
    )


class APIBaseTests(APITestCase):
    def setUp(self):
        self.process = subprocess.Popen(["python", "manage.py", "runserver"])
        sleep(2)

    def tearDown(self):
        os.kill(self.process.pid, 9)

    def test_api_version_check(self):
        """
        GET of /v2 should return a 200 response
        """
        url = reverse("django_oci:api_version_check")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class APIPushTests(APITestCase):
    def setUp(self):
        self.repository = "vanessa/container"
        self.image = os.path.join(here, "busybox_latest.sif")
        self.config = os.path.join(here, "config.json")

        # Read binary data and calculate sha256 digest
        with open(self.image, "rb") as fd:
            self.data = fd.read()
        self.digest = calculate_digest(self.data)

    def test_push_single_monolithic_post(self):
        """
        POST /v2/<name>/blobs/uploads/
        """

        def push(digest, data, content_type="application/octet-stream"):
            url = "http://127.0.0.1:8000%s?digest=%s" % (
                reverse("django_oci:blob_upload", kwargs={"name": self.repository}),
                digest,
            )
            print("Single Monolithic POST: %s" % url)
            headers = {
                "Content-Length": str(len(data)),
                "Content-Type": content_type,
            }
            response = requests.post(url, data=data, headers=headers)
            self.assertTrue(
                response.status_code
                in [status.HTTP_202_ACCEPTED, status.HTTP_201_CREATED]
            )

        # Push the image blob
        push(digest=self.digest, data=self.data)

        # Upload an image manifest
        with open(self.config, "r") as fd:
            content = fd.read().encode("utf-8")
        config_digest = calculate_digest(content)
        push(digest=config_digest, data=content)

    def test_push_post_then_put(self):
        """
        POST /v2/<name>/blobs/uploads/
        PUT /v2/<name>/blobs/uploads/
        """
        url = "http://127.0.0.1:8000%s" % (
            reverse("django_oci:blob_upload", kwargs={"name": self.repository})
        )
        print("POST to request session: %s" % url)
        headers = {"Content-Type": "application/octet-stream"}
        response = requests.post(url, headers=headers)

        # Location must be in response header
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue("Location" in response.headers)
        blob_url = "http://127.0.0.1:8000%s?digest=%s" % (
            response.headers["Location"],
            self.digest,
        )
        # PUT to upload blob url
        headers = {
            "Content-Length": str(len(self.data)),
            "Content-Type": "application/octet-stream",
        }
        print("PUT to upload: %s" % blob_url)
        response = requests.put(blob_url, data=self.data, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue("Location" in response.headers)

        download_url = response.headers["Location"]
        # TODO: test pull of location

    def test_push_chunked(self):
        """
        POST /v2/<name>/blobs/uploads/
        PATCH <location>
        PUT /v2/<name>/blobs/uploads/
        """
        url = "http://127.0.0.1:8000%s" % (
            reverse("django_oci:blob_upload", kwargs={"name": self.repository})
        )
        print("POST to request chunked session: %s" % url)
        headers = {"Content-Type": "application/octet-stream", "Content-Length": "0"}
        response = requests.post(url, headers=headers)

        # Location must be in response header
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue("Location" in response.headers)
        session_url = "http://127.0.0.1:8000%s" % response.headers["Location"]

        # Read the file in chunks, for each do a patch
        start = 0
        with open(self.image, "rb") as fd:
            for chunk in read_in_chunks(fd):
                if not chunk:
                    break

                end = start + len(chunk) - 1
                content_range = "%s-%s" % (start, end)
                headers = {
                    "Content-Range": content_range,
                    "Content-Length": str(len(chunk)),
                    "Content-Type": "application/octet-stream",
                }
                start = end + 1
                print("PATCH to upload content range: %s" % content_range)
                response = requests.patch(session_url, data=chunk, headers=headers)
                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
                self.assertTrue("Location" in response.headers)

        # Finally, issue a PUT request to close blob
        session_url = "%s?digest=%s" % (session_url, self.digest)
        response = requests.put(session_url)

        # Location must be in response header
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue("Location" in response.headers)

    def test_push_manifest(self):
        """
        PUT /v2/<name>/manifests/<reference>
        """
        url = "http://127.0.0.1:8000%s" % (
            reverse(
                "django_oci:image_manifest",
                kwargs={"name": self.repository, "tag": "latest"},
            )
        )
        print("PUT to create image manifest: %s" % url)

        # Calculate digest for config (yes, we haven't uploaded the blob, it's ok)
        with open(self.config, "r") as fd:
            content = fd.read()
        config_digest = calculate_digest(content.encode("utf-8"))

        # Prepare the manifest (already a text string)
        manifest = get_manifest(config_digest, self.digest)
        headers = {
            "Content-Type": "application/vnd.oci.image.manifest.v1+json",
            "Content-Length": str(len(manifest)),
        }
        response = requests.put(url, headers=headers, data=manifest)

        # Location must be in response header
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue("Location" in response.headers)
