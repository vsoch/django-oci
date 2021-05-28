"""
test_django-oci api
-------------------

Tests for `django-oci` conformance
"""

from rest_framework.test import APITestCase

from time import sleep
import subprocess
import sys
import os

here = os.path.abspath(os.path.dirname(__file__))

CONFORMANCE_BINARY_PATH = os.path.join(os.path.dirname(here), "conformance.test")
SKIP_CONFORMANCE = os.environ.get("DJANGO_OCI_SKIP_CONFORMANCE")


class ConformanceTests(APITestCase):
    def setUp(self):
        self.server_url = "127.0.0.1:8086"
        self.process = subprocess.Popen(
            ["python", "manage.py", "runserver", self.server_url]
        )
        sleep(2)

    def tearDown(self):
        os.kill(self.process.pid, 9)

    def test_conformance(self):
        """
        Given the conformance test binary exists, run tests
        """
        if not os.path.exists(CONFORMANCE_BINARY_PATH) and not SKIP_CONFORMANCE:
            sys.exit(
                "Conformance testing binary conformance.test not found, set DJANGO_OCI_SKIP_CONFORMANCE in environment to skip."
            )

        env = os.environ.copy()
        env["OCI_ROOT_URL"] = "http://" + self.server_url
        env["OCI_NAMESPACE"] = "vsoch/django-oci"
        env["OCI_DEBUG"] = "true"
        env["OCI_TEST_PUSH"] = "1"
        env["OCI_TEST_PULL"] = "1"
        env["OCI_TEST_CONTENT_DISCOVERY"] = "1"
        env["OCI_TEST_CONTENT_MANAGEMENT"] = "1"

        response = subprocess.call(CONFORMANCE_BINARY_PATH, env=env)
        self.assertEqual(response, 0)
