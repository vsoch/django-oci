# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.contrib import admin
from django.urls import include, re_path

urlpatterns = [
    re_path(r"^admin/", admin.site.urls),
    re_path(r"^", include("django_oci.urls", namespace="django_oci")),
]
