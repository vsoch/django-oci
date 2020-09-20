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
import os

here = os.path.abspath(os.path.dirname(__file__))


def calculate_digest(blob):
    """Given a blob (the body of a response) calculate the sha256 digest"""
    hasher = hashlib.sha256()
    hasher.update(blob)
    return hasher.hexdigest()


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

        # Read binary data and calculate sha256 digest
        with open(self.image, "rb") as fd:
            self.data = fd.read()
        self.digest = calculate_digest(self.data)

    def test_push_single_monolithic_post(self):
        """
        POST /v2/<name>/blobs/uploads/
        """
        url = "http://127.0.0.1:8000%s?digest=%s" % (
            reverse("django_oci:blob_upload", kwargs={"name": self.repository}),
            self.digest,
        )
        headers = {
            "Content-Length": str(len(self.data)),
            "Content-Type": "application/octet-stream",
        }
        print("Single Monolithic POST: %s" % url)
        response = requests.post(url, data=self.data, headers=headers)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

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
