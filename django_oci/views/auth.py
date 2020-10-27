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

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import authentication_classes, permission_classes
from django.views.decorators.cache import never_cache

from django_oci import settings
from django.http import HttpResponseForbidden

from django_oci.utils import get_server
from django_oci.auth import get_user, generate_jwt

import re


@authentication_classes([])
@permission_classes([])
class GetAuthToken(APIView):
    """Given a GET request for a token, validate and return it."""

    permission_classes = []
    allowed_methods = ("GET",)

    @never_cache
    def get(self, request, *args, **kwargs):
        """GET /auth/token"""
        print("GET /auth/token")
        user = get_user(request)

        # No token provided matching a user, no go
        if not user:
            return HttpResponseForbidden()

        # Formalate the jwt token response, with a unique id
        _ = request.GET.get("service")
        scope = request.GET.get("scope")

        # The scope should include the repository name, and permissions
        # "repository:vanessa/container:pull,push"
        match = re.match("repository:(?P<repository>.+):(?P<scope>.+)", scope)
        repository, scope = match.groups()
        scope = scope.split(",")

        # Generate domain name for auth server
        DOMAIN_NAME = get_server(request)
        auth_server = settings.AUTH_SERVER or "%s/auth/token" % DOMAIN_NAME

        # Generate the token data, a dict with token, expires_in, and issued_at
        data = generate_jwt(
            username=user.username,
            scope=scope,
            realm=auth_server,
            repository=repository,
        )
        return Response(status=200, data=data)
