---
title: "Storage"
pdf: true
toc: true
---

# Storage Options

Django-OCI aims to have several storage backends as options to store containers.
Currently, we start with just Filesystem support.

## Filesystem

Filesystem support is the default storage option, and is intended for smaller
registries that cannot use a possibly external resource like the cloud. You
don't need to change any settings to use filesystem storage, as it is the default.
