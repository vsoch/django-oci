---
title: "Authentication"
pdf: true
toc: true
---

# Authentication

Django oci takes a "docker style" version of OAuth 2.0. Details can be seen
in [this issue discussion](https://github.com/opencontainers/distribution-spec/issues/110#issuecomment-708691114).

## Custom Authentication

If you use Rest Framework for authentication, you'll need to add permission
and authentication classes on a per view bases, as Django OCI will remove
default authentication across all views to use it's own. This might be annoying,
but it's not such bad practice to be explicit about the authentication types
that you want. For more details [see here](https://www.django-rest-framework.org/api-guide/authentication/).
