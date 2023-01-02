---
title:  "Django-OCI Development"
date:   2020-10-12 01:51:21 -0500
categories: update
badges:
 - type: success
   tag: update
---

This is the first post to introduce a development version of Django-OCI!
Currently, the library supports only filesystem storage for an OCI compliant registry.
I hope to improve this project in the coming months with the following points.

<!--more-->

## Interfaces

I'd like to provide an example registry that also has interfaces to explore
containers.

## Storage Backends

It will be important to have support for more storage backends than the
typical filesystem.

## Authentication

Currently, there is no checking or authentication to interact with the registry,
which won't fly in production. This needs to be added.
