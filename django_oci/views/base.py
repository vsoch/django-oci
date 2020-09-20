# -*- coding: utf-8 -*-

from rest_framework.views import APIView
from rest_framework.response import Response

# from rest_framework import generics, serializers, viewsets, status
# from rest_framework.exceptions import PermissionDenied, NotFound
# from ratelimit.mixins import RatelimitMixin


class APIVersionCheck(APIView):
    """provide version support information based on response statuses.
    This endpoint should only allow GET requests.
    https://github.com/opencontainers/distribution-spec/blob/master/spec.md#api-version-check
    """

    permission_classes = []
    allowed_methods = ("GET",)

    def get(self, request, *args, **kwargs):
        headers = {"Docker-Distribution-API-Version": "registry/2.0"}
        return Response({"success": True})
