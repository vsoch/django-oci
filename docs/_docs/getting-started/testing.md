---
title: "Testing"
pdf: true
toc: true
---

# Testing

## Python Tests

Tests are located in [tests](https://github.com/vsoch/django-oci/tree/master/tests) and can be run with:

```bash
source <YOURVIRTUALENV>/bin/activate
pip install -r requirements.txt
./runtests.sh
```

## Conformance

Conformance testing is provided by the [distribution-spec](https://github.com/opencontainers/distribution-spec) repository.
This means that you would want to start the server, and then clone this repository and run the tests. Complete
instructions are [here](https://github.com/opencontainers/distribution-spec/tree/master/conformance), and the results
of the latest tests can be seen under [conformance](https://vsoch.github.io/django-oci/conformance), which will be updated
with each release. An example is provided below:

### 1. Start the Server
First run your example server as follows (cleaning up the test database):

```bash
rm -rf db-test.sqlite3
python manage.py makemigrations django_oci
python manage.py makemigrations
python manage.py migrate
python manage.py migrate django_oci
python manage.py runserver
```
```
System check identified no issues (0 silenced).
October 10, 2020 - 20:52:20
Django version 3.1.1, using settings 'tests.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

This tells us that the developmment server is running on port 8000 on localhost. We will
need this for next steps!

### 2. Clone and build conformance tests

Somewhere else on your machine, clone the distribution-spec repository and then
cd into conformance.

```bash
git clone https://github.com/opencontainers/distribution-spec/
cd distribution-spec/conformance
```
You'll need to [install GoLang](https://golang.org/doc/install) and then compile the test code into `conformance.test`:

```bash
go test -c
```

Then export environment variables that we need for tests:

```bash
# Registry details
export OCI_ROOT_URL="http://127.0.0.1:8000/"
export OCI_NAMESPACE="vsoch/django-oci"
#export OCI_USERNAME="myuser"
#export OCI_PASSWORD="mypass"

# Which workflows to run
export OCI_TEST_PUSH=1
export OCI_TEST_PULL=1
export OCI_TEST_CONTENT_DISCOVERY=1
export OCI_TEST_CONTENT_MANAGEMENT=1

# Extra settings
#export OCI_HIDE_SKIPPED_WORKFLOWS=0
#export OCI_DEBUG=0
#export OCI_DELETE_MANIFEST_BEFORE_BLOBS=0
```

And then you'll have a report (html and xml) in the test folder! This can be submit to the
distribution spec respository to validate your registry.
