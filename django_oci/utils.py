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

import logging
import re

logger = logging.getLogger(__name__)


# Regular expressions to parse registry, collection, repo, tag and version
_docker_uri = re.compile(
    "(?:(?P<registry>[^/@]+[.:][^/@]*)/)?"
    "(?P<collection>(?:[^:@/]+/)+)?"
    "(?P<repo>[^:@/]+)"
    "(?::(?P<tag>[^:@]+))?"
    "(?:@(?P<version>.+))?"
    "$"
)

# Reduced to match registry:port/repo or registry.com/repo
_reduced_uri = re.compile(
    "(?:(?P<registry>[^/@]+[.:][^/@]*)/)?"
    "(?P<repo>[^:@/]+)"
    "(?::(?P<tag>[^:@]+))?"
    "(?:@(?P<version>.+))?"
    "$"
    "(?P<collection>.)?"
)

# Default
_default_uri = re.compile(
    "(?:(?P<registry>[^/@]+)/)?"
    "(?P<collection>(?:[^:@/]+/)+)"
    "(?P<repo>[^:@/]+)"
    "(?::(?P<tag>[^:@]+))?"
    "(?:@(?P<version>.+))?"
    "$"
)


def set_default(item, default, use_default):
    """if an item provided is None and boolean use_default is set to True,
    return the default. Otherwise, return the item.
    """
    if item is None and use_default:
        return default
    return item


def get_server(request):
    """Given a request, parse it to determine the server name and using http/https"""
    scheme = request.is_secure() and "https" or "http"
    return f"{scheme}://{request.get_host()}"


def parse_content_range(content_range):
    """Given a content range, match based on regular expression and return
    parsed start, end (both int)
    """
    # Ensure range matches regular expression
    if not re.search("^[0-9]+-[0-9]+$", content_range):
        raise ValueError

    # Parse the content range into numbers
    return [int(x.strip()) for x in content_range.strip().split("-")]


def parse_image_name(
    image_name,
    tag=None,
    version=None,
    defaults=True,
    ext="sif",
    default_collection="library",
    default_tag="latest",
    base=None,
    lowercase=True,
):

    """return a collection and repo name and tag
    for an image file.

    Parameters
    =========
    image_name: a user provided string indicating a collection,
                image, and optionally a tag.
    tag: optionally specify tag as its own argument
         over-rides parsed image tag
    defaults: use defaults "latest" for tag and "library"
              for collection.
    base: if defined, remove from image_name, appropriate if the
          user gave a registry url base that isn't part of namespace.
    lowercase: turn entire URI to lowercase (default is True)
    """

    # Save the original string
    original = image_name

    if base is not None:
        image_name = image_name.replace(base, "").strip("/")

    # If a file is provided, remove extension
    image_name = re.sub("[.](img|simg|sif)", "", image_name)

    # Parse the provided name
    uri_regexes = [_reduced_uri, _default_uri, _docker_uri]

    for r in uri_regexes:
        match = r.match(image_name)
        if match:
            break

    if not match:
        logger.warning('Could not parse image "%s"! Exiting.' % image_name)
        return

    # Get matches
    registry = match.group("registry")
    collection = match.group("collection")
    repo_name = match.group("repo")
    repo_tag = tag or match.group("tag")
    version = version or match.group("version")

    # A repo_name is required
    assert repo_name

    # If a collection isn't provided
    collection = set_default(collection, default_collection, defaults)
    repo_tag = set_default(repo_tag, default_tag, defaults)

    # The collection, name must be all lowercase
    if lowercase:
        collection = collection.lower().rstrip("/")
        repo_name = repo_name.lower()
        repo_tag = repo_tag.lower()
    else:
        collection = collection.rstrip("/")

    if version is not None:
        version = version.lower()

    # Piece together the uri base
    if registry is None:
        uri = "%s/%s" % (collection, repo_name)
    else:
        uri = "%s/%s/%s" % (registry, collection, repo_name)

    url = uri

    # Tag is defined
    if repo_tag is not None:
        uri = "%s:%s" % (url, repo_tag)

    # Version is defined
    storage_version = None
    if version is not None:
        uri = "%s@%s" % (uri, version)
        storage_version = "%s.%s" % (uri, ext)

    # A second storage URI honors the tag (:) separator

    storage = "%s.%s" % (uri, ext)
    return {
        "collection": collection,
        "original": original,
        "registry": registry,
        "image": repo_name,
        "url": url,
        "tag": repo_tag,
        "version": version,
        "storage": storage_version or storage,
        "uri": uri,
    }
