"""
test_django-oci api
-------------------

Tests for `django-oci` api.
"""

from django.urls import reverse
from django.contrib.auth.models import User
from django_oci import settings
from rest_framework import status
from rest_framework.test import APITestCase
from django.test.utils import override_settings
from time import sleep
from unittest import skipIf
import subprocess
import requests
import hashlib
import base64
import json
import os
import re

here = os.path.abspath(os.path.dirname(__file__))

# Boolean from environment that determines authentication required variable
auth_regex = re.compile('(\w+)[:=] ?"?([^"]+)"?')

# Important: user needs to be created globally to be seen
user, _ = User.objects.get_or_create(username="dinosaur")
token = str(user.auth_token)


def calculate_digest(blob):
    """Given a blob (the body of a response) calculate the sha256 digest"""
    hasher = hashlib.sha256()
    hasher.update(blob)
    return hasher.hexdigest()


def get_auth_header(username, password):
    """django oci requires the user token as the password to generate a longer
    auth token that will expire after some number of seconds
    """
    auth_str = "%s:%s" % (username, password)
    auth_header = base64.b64encode(auth_str.encode("utf-8"))
    return {"Authorization": "Basic %s" % auth_header.decode("utf-8")}


def get_authentication_headers(response):
    """Given a requests.Response, assert that it has status code 401 and
    provides the Www-Authenticate header that can be parsed for the request
    """
    assert response.status_code == 401
    assert "Www-Authenticate" in response.headers
    matches = dict(auth_regex.findall(response.headers["Www-Authenticate"]))
    for key in ["scope", "realm", "service"]:
        assert key in matches

    # Prepare authentication headers and get token
    headers = get_auth_header(user.username, token)
    url = "%s?service=%s&scope=%s" % (
        matches["realm"],
        matches["service"],
        matches["scope"],
    )
    # With proper headers should be 200
    auth_response = requests.get(url, headers=headers)
    assert auth_response.status_code == 200
    body = auth_response.json()

    # Make sure we have the expected fields
    for key in ["token", "expires_in", "issued_at"]:
        assert key in body

    # Formulate new auth header
    return {"Authorization": "Bearer %s" % body["token"]}


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
        GET of /v2 should return a 200 response.
        """
        url = reverse("django_oci:api_version_check")
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class APIPushTests(APITestCase):
    def push(
        self,
        digest,
        data,
        content_type="application/octet-stream",
        test_response=True,
        extra_headers={},
    ):
        url = "http://127.0.0.1:8000%s?digest=%s" % (
            reverse("django_oci:blob_upload", kwargs={"name": self.repository}),
            digest,
        )
        print("Single Monolithic POST: %s" % url)
        headers = {
            "Content-Length": str(len(data)),
            "Content-Type": content_type,
        }
        headers.update(extra_headers)
        response = requests.post(url, data=data, headers=headers)
        if test_response:
            self.assertTrue(
                response.status_code
                in [status.HTTP_202_ACCEPTED, status.HTTP_201_CREATED]
            )
        return response

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
        auth_headers = get_authentication_headers(response)
        headers.update(auth_headers)
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
        headers.update(auth_headers)
        print("PUT to upload: %s" % blob_url)
        response = requests.put(blob_url, data=self.data, headers=headers)

        # This should allow HTTP_202_ACCEPTED too
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue("Location" in response.headers)
        download_url = add_url_prefix(response.headers["Location"])
        response = requests.get(download_url, headers=auth_headers)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test upload request from another repository
        non_standard_name = "conformance-aedf05b6-6996-4dae-ad18-70a4db9e9061"
        url = "http://127.0.0.1:8000%s" % (
            reverse("django_oci:blob_upload", kwargs={"name": non_standard_name})
        )
        url = "%s?mount=%s&from=%s" % (url, self.digest, self.repository)
        print("POST to request mount from another repository: %s" % url)
        headers = {"Content-Type": "application/octet-stream"}
        response = requests.post(url, headers=headers)
        auth_headers = get_authentication_headers(response)
        headers.update(auth_headers)
        response = requests.post(url, headers=headers)
        assert "Location" in response.headers

        assert non_standard_name in response.headers["Location"]
        download_url = add_url_prefix(response.headers["Location"])
        response = requests.get(download_url, headers=auth_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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
        auth_headers = get_authentication_headers(response)
        headers.update(auth_headers)
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
                headers.update(auth_headers)
                start = end + 1
                print("PATCH to upload content range: %s" % content_range)
                response = requests.patch(session_url, data=chunk, headers=headers)
                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
                self.assertTrue("Location" in response.headers)

        # Finally, issue a PUT request to close blob
        session_url = "%s?digest=%s" % (session_url, self.digest)
        response = requests.put(session_url, headers=auth_headers)

        # Location must be in response header
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue("Location" in response.headers)

    def test_push_view_delete_manifest(self):
        """
        PUT /v2/<name>/manifests/<reference>
        DELETE /v2/<name>/manifests/<reference>
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
        manifest_reference = "sha256:%s" % calculate_digest(manifest.encode("utf-8"))
        headers = {
            "Content-Type": "application/vnd.oci.image.manifest.v1+json",
            "Content-Length": str(len(manifest)),
        }
        response = requests.put(url, headers=headers, data=manifest)

        auth_headers = get_authentication_headers(response)
        headers.update(auth_headers)
        response = requests.put(url, headers=headers, data=manifest)

        # Location must be in response header
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue("Location" in response.headers)

        # test manifest download
        response = requests.get(url, headers=auth_headers).json()
        for key in ["schemaVersion", "config", "layers", "annotations"]:
            assert key in response

        # Retrieve newly created tag
        tags_url = "http://127.0.0.1:8000%s" % (
            reverse("django_oci:image_tags", kwargs={"name": self.repository})
        )
        print("GET to list tags: %s" % tags_url)
        tags = requests.get(tags_url, headers=auth_headers)
        self.assertEqual(tags.status_code, status.HTTP_200_OK)
        tags = tags.json()
        for key in ["name", "tags"]:
            assert key in tags

        # First delete tag (we are allowed to have an untagged manifest)
        response = requests.delete(url, headers=auth_headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Finally, delete the manifest
        url = "http://127.0.0.1:8000%s" % (
            reverse(
                "django_oci:image_manifest",
                kwargs={"name": self.repository, "reference": manifest_reference},
            )
        )
        response = requests.delete(url, headers=auth_headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_push_single_monolithic_post(self):
        """
        POST /v2/<name>/blobs/uploads/
        """
        # Push the image blob, should return 401 without authentication
        response = self.push(digest=self.digest, data=self.data, test_response=False)
        headers = get_authentication_headers(response)
        response = self.push(
            digest=self.digest,
            data=self.data,
            test_response=False,
            extra_headers=headers,
        )
        assert response.status_code == 201
        assert "Location" in response.headers
        download_url = add_url_prefix(response.headers["Location"])

        response = requests.get(download_url, headers=headers if headers else None)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Upload an image manifest
        with open(self.config, "r") as fd:
            content = fd.read().encode("utf-8")
        config_digest = calculate_digest(content)
        self.push(digest=config_digest, data=content, extra_headers=headers)

    def setUp(self):
        self.repository = "vanessa/container"
        self.image = os.path.abspath(
            os.path.join(here, "..", "examples", "singularity", "busybox_latest.sif")
        )
        self.config = os.path.abspath(
            os.path.join(here, "..", "examples", "singularity", "config.json")
        )

        # Read binary data and calculate sha256 digest
        with open(self.image, "rb") as fd:
            self.data = fd.read()
        self._digest = calculate_digest(self.data)
        self.digest = "sha256:%s" % self._digest


def add_url_prefix(download_url):
    if not download_url.startswith("http"):
        download_url = "http://127.0.0.1:8000%s" % download_url
    return download_url
