---
title: Design
pdf: true
toc: false
---

# Design

This document aims to answer questions about design. There is some leeway with respect
to how the models are designed.

## Models

In the case that we have repositories, blobs, and image manifests that connect the two,
you could imagine a design that has blobs shared between images and repositories, or one
that is more redundant to keep a storage namespace based on repositories, that way no two
repositories can share the exact same blob. Or more specifically:

- Having blobs linked 1:1 to a repository, and then referenced in Image Manifests only belonging to that repository (you wouldn't need to worry about blob sharing across repositories, and cleanup would be limited to ensuring the blob only isn't needed by the repository in question)
 - Having blobs linked to Image Manifests, which are linked to Repositories.
 - Having blobs not linked to any Image Manifest or Repository and shared amongst all blobs (and for this implementation idea you would need to ensure that blobs are not deleted that are still being used, and that there aren't any security loopholes with someone uploading a blob that would be used by another repository.

While the last design is more space efficient, is does potentially introduce security and cleanup
issues when sharing blobs. For this reason, we choose the second design - by way of the distribution-spec
having the repository name as a parameter to most requests, we can easily link each of blobs and Image manifests
to a repository directly. For more detail about the distribution-spec, we recommend that you look
at the [distribution-spec repository](https://github.com/opencontainers/distribution-spec/).
The remainder of this section briefly discusses models.

### Repository

A repository is a namespace like `myorg/myrepo` that has one or more image manifests,
or lists of blobs associated with a set of metadata. A repository will be owned by a user,
and optionally have additional contributors, and finally, be optionally private.
These last set of features are not yet implemented.

## Images

An image model is technically referring to an image manifest. This means it points to one
or more blobs, and has metadata about an image. The image manifest itself is stored in the 
exact same byte stream as it's provided (BinaryField), and the blobs and annotations are extracted
after parsing from string to json. An image (manifest) is also directly linked (or owned)
by a repository, and each manifest has a many to many relationship to point to one or more blobs

## Blobs

A blob is a binary (a FileField) along with a content type that is uploaded by a client.
The general workflow for a push is to provide a set of blobs associated with an image manifest
and repository. For the implementation here, we link blobs off the bat with a repository (and
storage honors this structure as well) and then either use POST, PUT, or PATCH to do a monolithic
or chunked upload. Blobs are then referenced in image manifests and can be requested for pull
by an oci compliant client. To eventually support remote file storage, blobs have both a datafile
(FileField) and a remotefile that would allow for a remote address (not yet used).

## Tag

A tag is typically a small string to describe a version of a manifest, e.g., "latest."
Tags fall under the general description of a "digest" which can also include a sha256 sum.
In the case of the implementation here, Tags are represented in their own table, and 
have fields for a name, and then a foreign key to a particular image. This means
that one image can have more than one tag, and tags are not shared between images.

## Annotation

Akin to a tag, an annotation also stores a foreign key to a particular image, but
instead of just a name, we hold a key and value pair.  For both these strategies, while
it might be redundant to store "the same" tag or annotation for different repositories,
this approach is taken to mirror the design choice to not have shared model instances
between repositories. This design choice could of course change if there is compelling
reason.

