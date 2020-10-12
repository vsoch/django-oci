---
title: "Options"
pdf: true
toc: true
---

# Options

The following options are available for you to define under a `DJANGO_OCI`
dictionary in your Django settings. For example, to change the `MEDIA_ROOT`
(where we store blobs, sessions, etc. for a filesystem storage) and the cache
directory you might do  the following:

```python
DJANGO_OCI = {
    "STORAGE_BACKEND": "filesystem",
    # Change default "images" folder to "data"
    "MEDIA_ROOT": "data",
    # Set a cache directory, otherwise defaults to MEDIA_ROOT + /cache
    "CACHE_DIR": "cache",
}
```

## Options Available

The following options are available for you to change or configure. If there is a functionality
missing that you'd like to see here, please [open an issue]({{ site.repo }}/issues).


| name | description | type |default |
|------|-------------|------|--------|
|URL_PREFIX | Url base prefix | string | v2 |
|SPEC_VERSION |  Version of distribution spec | string | 1 |
|PRIVATE_ONLY| Only allow private repositories (not implemented yet) | boolean | False |
|AUTHENTICATED_USER | Custom class for user (only define if you have one ) | string | None |
|CONTENT_TYPES | Allowed content types to upload as layers | list of strings | ["application/octet-stream"] |
|IMAGE_MANIFEST_CONTENT_TYPE | Image Manifest content type | string | application/vnd.oci.image.manifest.v1+json |
|STORAGE_BACKEND | what storage backend to use | string | filesystem |
|DOMAIN_URL | the default domain url to use | string | http://127.0.0.1:8000 |
|MEDIA_ROOT | Media root (if saving images on filesystem | string | images |
|CACHE_DIR | Set a custom cache directory | string | MEDIA_ROOT + /cache |
|SESSION_EXPIRES_SECONDS | The number of seconds a session (upload request) is valid (10 minutes) | integer | 600 |
|DISABLE_TAG_MANIFEST_DELETE| Don't allow deleting of manifest tags | boolean | False |
|DEFAULT_CONTENT_TYPE| Default content type is application/octet-stream | string | application/octet-stream|

Some of these are not yet developed (e.g., `PRIVATE_ONLY` and others are unlikely to ever change
(e.g., `DEFAULT_CONTENT_TYPE` but are provided in case you want to innovate or try something new.
