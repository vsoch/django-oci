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

from rest_framework import renderers
from rest_framework.negotiation import BaseContentNegotiation


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """Important! This class is not used, however if you want to validate
    (or allow) any media type (e.g., the server doesn't return 406) you
    can set this as the default content negotiation for any view.

    content_negotiation_class = IgnoreClientContentNegotiation
    """

    def select_parser(self, request, parsers):
        """Return the first parser (usually application/json)"""
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        """Return the first renderer (usually application/json)"""
        return (renderers[0], renderers[0].media_type)


class ManifestRenderer(renderers.BaseRenderer):
    """A ManifestRenderer is provided to the ImageManifest views, which need
    to accept a content type for the image manifest. Without this
    renderer, Django will return 406
    """

    media_type = "application/vnd.oci.image.manifest.v1+json"
    format = None
    charset = None
    render_style = "binary"

    def render(self, data, media_type=None, renderer_context=None):
        return data
