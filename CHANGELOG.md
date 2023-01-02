# Changelog

This is a manually generated log to track changes to the repository for each release.
Each section should include general headers such as **Implemented enhancements**
and **Merged pull requests**. All closed issued and bug fixes should be
represented by the pull requests that fixed them.
Critical items to know are:

 - renamed commands
 - deprecated / removed commands
 - changed defaults
 - backward incompatible changes
 - migration guidance
 - changed behaviour

## [master](https://github.com/vsoch/django-oci/tree/master)
 - unpinning pyjwt version (0.0.17)
   - updating license headers
   - support for Django 4.0+
 - Better tweak MANIFEST for upload to not include pycache (0.0.16)
 - Bug with filesystem save (saving without full image path) (0.0.15)
 - Adding mount and HEAD new endpoints for distribution spec (0.0.14)
 - View specific permission (pull,push) required (0.0.13)
 - Adding Django ratelimit to protect views (0.0.12)
 - Added authentication (0.0.11)
 - Django OCI core release without authentication (0.0.1)
 - skeleton release  (0.0.0)
