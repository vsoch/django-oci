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
from django.urls import resolve
from django.contrib.auth.models import User

from django_oci import settings
from django_oci.utils import get_server
from django_oci.models import Repository

from rest_framework.authtoken.models import Token
from rest_framework.response import Response

from django.middleware import cache

from datetime import datetime
import uuid
import base64
import re
import time
import jwt


def is_authenticated(
    request, repository=None, must_be_owner=True, repository_exists=True, scopes=None
):
    """
    Function to check if a request is authenticated, a repository and the request is required.
    Returns a boolean to indicate if the user is authenticated, and a response with
    the challenge if not. If allow_if_private is True, we only allow access to users
    that are owners or contributors, regardless of having a valid token.

    Arguments:
    ==========
    request (requests.Request)    : the Request object to inspect
    repository (str or Repository): the name of a repository or instance
    must_be_owner (bool)          : if must be owner is true, requires push
    reposity_exists (bool)        : flag to indicate that the repository exists.
    """
    # Scopes default to push and pull, more conservative
    scopes = scopes or ["push", "pull"]

    # Derive the view name from the request PATH_INFO
    func, two, three = resolve(request.META["PATH_INFO"])
    view_name = "%s.%s" % (func.__module__, func.__name__)

    # If authentication is disabled, return the original view
    if settings.DISABLE_AUTHENTICATION or view_name not in settings.AUTHENTICATED_VIEWS:
        return True, None, None

    # Ensure repository is valid, only if provided
    name = repository
    if repository is not None and repository_exists and isinstance(repository, str):
        try:
            repository = Repository.objects.get(name=repository)
            name = repository.name
        except Repository.DoesNotExist:
            return False, Response(status=404), None

    # Case 2: Already has a jwt valid token
    is_valid, user = validate_jwt(request, repository, must_be_owner)
    if is_valid:
        return True, None, user

    # Case 3: False and response will return request for auth
    user = get_user(request)
    if not user:
        headers = {"Www-Authenticate": get_challenge(request, name, scopes=scopes)}
        return False, Response(status=401, headers=headers), user

    # Denied for any other reason
    return False, Response(status=403), user


def generate_jwt(username, scope, realm, repository):
    """Given a username, scope, realm, repository, and service, generate a jwt
    token to return to the user with a default expiration of 10 minutes.

    Arguments:
    ==========
    username (str)  : the user's username to add under "sub"
    scope (list)    : a list of scopes to require (e.g., ['push, pull'])
    realm (str)     : the authentication realm, typically <server>/auth
    repository (str): the repository name
    """
    # The jti expires after TOKEN_EXPIRES_SECONDS
    issued_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    filecache = cache.caches["django_oci_upload"]
    jti = str(uuid.uuid4())
    filecache.set(jti, "good", timeout=settings.TOKEN_EXPIRES_SECONDS)
    now = int(time.time())
    expires_at = now + settings.TOKEN_EXPIRES_SECONDS

    # import jwt and generate token
    # https://tools.ietf.org/html/rfc7519#section-4.1.5
    payload = {
        "iss": realm,  # auth endpoint
        "sub": username,
        "exp": expires_at,
        "nbf": now,
        "iat": now,
        "jti": jti,
        "access": [{"type": "repository", "name": repository, "actions": scope}],
    }
    token = jwt.encode(payload, settings.JWT_SERVER_SECRET, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return {
        "token": token,
        "expires_in": settings.TOKEN_EXPIRES_SECONDS,
        "issued_at": issued_at,
    }


def validate_jwt(request, repository, must_be_owner):
    """Given a jwt token, decode and validate

    Arguments:
    ==========
    request (requests.Request)    : the Request object to inspect
    repository (models.Repository): the repository instance
    must_be_owner (bool)          : if True, requires additional push scope
    """
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if re.search("bearer", header, re.IGNORECASE):
        encoded = re.sub("bearer", "", header, flags=re.IGNORECASE).strip()

        # Any reason not valid will issue an error here
        try:
            decoded = jwt.decode(
                encoded, settings.JWT_SERVER_SECRET, algorithms=["HS256"]
            )
        except Exception as exc:
            print("jwt could no be decoded, %s" % exc)
            return False, None

        # Ensure that the jti is still valid
        filecache = cache.caches["django_oci_upload"]
        if not filecache.get(decoded.get("jti")) == "good":
            print("Filecache with jti not found.")
            return False, None

        # The user must exist
        try:
            user = User.objects.get(username=decoded.get("sub"))
        except User.DoesNotExist:
            print("Username %s not found" % decoded.get("sub"))
            return False, None

        # If a repository exists, the user must be an owner
        if (
            isinstance(repository, Repository)
            and (repository.private or must_be_owner)
            and user not in repository.owners.all()
            and user not in repository.contributors.all()
        ):
            print("Username %s not in repository owners" % decoded.get("sub"))
            return False, None

        # If repository is not defined and must be owner, no go
        if repository is None and must_be_owner:
            print("Repository is None and must be owner")
            return False, None

        # TODO: any validation needed for access type?
        requested_name = decoded.get("access", [{}])[0].get("name")
        if isinstance(repository, Repository) and repository.name != requested_name:
            print("Repository name is not equal to requested name.")
            return False, None

        # Do we have the correct permissions?
        requested_permission = decoded.get("access", [{}])[0].get("actions")
        if must_be_owner and "push" not in requested_permission:
            print("Must be owner and push not in requested permissions")
            return False, None
        return True, user

    return False, None


def get_user(request):
    """Given a request, read the Authorization header to get the base64 encoded
    username and token (password) which is a basic auth. If we return the user
    object, the user is successfully authenticated. Otherwise, return None.
    and the calling function should return Forbidden status.

    Arguments:
    ==========
    request (requests.Request)    : the Request object to inspect
    """
    header = request.META.get("HTTP_AUTHORIZATION", "")

    if re.search("basic", header, re.IGNORECASE):
        encoded = re.sub("basic", "", header, flags=re.IGNORECASE).strip()
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, token = decoded.split(":", 1)
        try:
            token = Token.objects.get(key=token)
            if token.user.username == username:
                return token.user
        except:
            pass


def get_token(request):
    """The same as validate_token, but return the token object to check the
    associated user.

    Arguments:
    ==========
    request (requests.Request)    : the Request object to inspect
    """
    # Coming from HTTP, look for authorization as bearer token
    token = request.META.get("HTTP_AUTHORIZATION")

    if token:
        try:
            return Token.objects.get(key=token.replace("BEARER", "").strip())
        except Token.DoesNotExist:
            pass

    # Next attempt - try to get token via user session
    elif request.user.is_authenticated and not request.user.is_anonymous:
        try:
            return Token.objects.get(user=request.user)
        except Token.DoesNotExist:
            pass


def get_challenge(request, repository, scopes=["pull", "push"]):
    """Given an unauthenticated request, return a challenge in
    the Www-Authenticate header

    Arguments:
    ==========
    request (requests.Request): the Request object to inspect
    repository (str)          : the repository name
    scopes (list)             : list of scopes to return
    """
    DOMAIN_NAME = get_server(request)
    if not isinstance(scopes, list):
        scopes = [scopes]
    auth_server = settings.AUTH_SERVER or "%s/auth/token" % DOMAIN_NAME
    return 'realm="%s",service="%s",scope="repository:%s:%s"' % (
        auth_server,
        DOMAIN_NAME,
        repository,
        ",".join(scopes),
    )
