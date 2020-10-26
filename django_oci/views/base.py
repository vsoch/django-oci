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


class APIVersionCheck(APIView):
    """provide version support information based on response statuses.
    This endpoint should only allow GET requests.
    https://github.com/opencontainers/distribution-spec/blob/master/spec.md#api-version-check
    """

    permission_classes = []
    allowed_methods = ("GET",)

    def get(self, request, *args, **kwargs):
        headers = {"Docker-Distribution-API-Version": "registry/2.0"}
        return Response({"success": True}, headers=headers)
