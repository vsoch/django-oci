---
title: Introduction
pdf: true
toc: false
---

# Introduction

## Opencontainers

Containers have really taken off in the first two decades of the century. They've done so well, in fact, that
it quickly became apparent that many different entities would need to better work together on standards for container
runtimes, interactions, and even registries. This is the rationale for the creation of the [opencontainers](https://opencontainers.org/) initiative in 2015.  You can read [more about the effort here](https://opencontainers.org/about/overview/) or in their own words:

> The Open Container Initiative is an open governance structure for the express purpose of creating open industry standards around container formats and runtimes. Established in June 2015 by Docker and other leaders in the container industry, the OCI currently contains two specifications: the Runtime Specification (runtime-spec) and the Image Specification (image-spec). The Runtime Specification outlines how to run a “filesystem bundle” that is unpacked on disk. At a high-level an OCI implementation would download an OCI Image then unpack that image into an OCI Runtime filesystem bundle. At this point the OCI Runtime Bundle would be run by an OCI Runtime.

The relevant specification for django-oci is the [distribution spec](https://github.com/opencontainers/distribution-spec), which defines the interactions that some client should be able to have with a container registry.

## Singularity containers

Also back around 2016, containers were badly needed for science. The main difference here is that most scientists would want to
run containers on big shared clusters, high performance computing resources, where it was a security issue to use a root daemon, which is the way that Docker worked at the time. Additionally, Docker provided a level of isolation that made it hard to interact
with drivers and traditional technologies like MPI, or even the cluster manager.

This led to the creation of Singularity containers, which were first under the umbrella of Lawrence Berkeley National Lab, and now the [software is supported](https://sylabs.io/guides/3.5/user-guide/quick_start.html) by the company Sylabs. During these years, community members such as the creator of this software aimed to provide registries just for Singularity containers, namely a hosted service, [Singularity Hub](https://singularity-hub.org) and an open source derivation, [Singularity Registry Server](https://singularityhub.github.io/sregistry). Singularity Hub was supported by the Singularity software from the getgo, as the creator was one of the early developers, and Singularity Registry Server originally implemented this same API, eventually adding the Sylabs [library API](https://sylabs.io/guides/3.6/user-guide/cloud_library.html) to allow for another means to pull containers.

## The Distribution Spec
Although Singularity was designed differently (one read-only binary instead of many layers, with one writable), the basic idea that we would want a registry to interact with Singularity containers still holds true. This is also true for other facets of the Singularity software, namely having support for the [runtime spec](https://sylabs.io/guides/3.6/user-guide/oci_runtime.html) as well. The want for a registry to support the  [distribution spec](https://github.com/opencontainers/distribution-spec) thus started to trickle into [issue boards](https://github.com/singularityhub/sregistry/issues/285). The developer of Singularity Registry Server didn't want to hard code support into just that registry, but instead provide a flexible module for any Django developer to use. This is the rationale behind creation of this library, [django-oci](https://github.com/vsoch/django-oci).

<br>

# Goals

While still in early in development, django-oci aims to meet the following goals:

 - provide a registry that conforms to the distribution-spec, passing conformance testing
 - make customization easy for the developer user
 - provide numerous storage backends

Most of these are still under development! If you'd like to help, please [let us know!]({{site.repo}}/issues).
