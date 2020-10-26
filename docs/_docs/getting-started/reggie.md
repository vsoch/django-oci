---
title: "Example Clients"
pdf: true
toc: true
---

# Clients

While there is no official client, here we discuss several strategies for
communicating with your django-oci registry.


## Python Requests

If you don't want a lot of extra dependnecies, Python requests is a good way to go!
You can look at the [api tests](https://github.com/vsoch/django-oci/blob/master/tests/test_api.py) to see 
updated examples for push, pull, and other content
management.

## Reggie

If you are looking for a more structured Python client to interact with an [opencontainers/distribution-spec](https://github.com/opencontainers/distribution-spec) registry like django-oci, [oci-python](https://github.com/vsoch/oci-python) serves a client, Reggie (python) - "the saint of content management" that mimics the official [Reggie client](https://github.com/bloodorangeio/reggie) to interact with an OCI registry. You can read [complete documentation served at the repository](https://vsoch.github.io/oci-python/docs/getting-started#distribution-specification)
and keep reading for a small tutorial.

### 1. Start a server

Let's first start a django-oci server.
Note that at the time of this writing, django-oci does not have authentication
implemented yet, so push/pull endpoints will work without it.
Here is a quick set of steps to get a server running.

```bash
git clone https://github.com/vsoch/django-oci
cd django-oci

# Install dependencies
python -m venv env
source env/bin/activate
pip install -r requirements.txt
pip install opencontainers

# Disable authentication for the demo
export DISABLE_AUTHENTICATION=yes

# Database migrations
python manage.py makemigrations
python manage.py makemigrations django_oci
python manage.py migrate
python manage.py runserver
```
```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
October 17, 2020 - 21:53:15
Django version 3.1.2, using settings 'tests.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

If you need to customize the port:

```bash
python manage.py runserver 127.0.0.0:9999
```

This should get a development server running! Also note that we are installing reggie
with `pip install opencontainers`. Now you can open another Python
interactive terminal (I like ipython) and test the opencontainers reggie client.
You'll again want to source the same environment, and probably install ipython
for a nicer terminal experience.

```bash
source env/bin/activate
pip install ipython
ipython
```
```python
from opencontainers.distribution.reggie import *
client = NewClient("http://127.0.0.1:8000", WithDefaultName("myorg/myrepo"), WithDebug(True))
```

You can see that the client settings are under the "Config" attribute.
```
client.Config.DefaultName
# 'myorg/myrepo'

client.Config.Debug
# True
```

Next, let's walk through a few basic requests to demonstrate how Reggie Python works.
These next steps assume you've created the client above, and the server is still running.

#### 2. Ping the registry

You can ping a registry generally at the `/v2/` endpoint. The registry should
return a 200 response to say "Hello, yes I'm here!" Let's prepare and issue the request:

```python
req = client.NewRequest("GET", "/v2/")
response = client.Do(req)

# We get a 200 response!
response
# <Response [200]>

response.json()
{'success': True}
```

Let's now try more substantial requests.

#### 3. Upload a blob with POST then PUT

Let's walk through creating and uploading a blob to our registry. For fun to show
that the blob can be for other kinds of containers (not just Docker) let's upload a Singularity image,
which is provided in the examples folder of django-oci. Let's prepare the path for
the image and config.json from the base of the repository.

```python
import os
image = os.path.abspath(os.path.join("examples", "singularity", "busybox_latest.sif"))
config = os.path.abspath(os.path.join("examples", "singularity", "config.json"))
```

Next, prepare the request to upload.
Since this is a fairly small image we will use a single POST request. Remember that you
are allowed to do a single monolithic upload, a POST then PUT, or a chunked upload.

```python
# Request an upload session URL
req = client.NewRequest("POST", "/v2/<name>/blobs/uploads/")

req.url
# 'http://localhost:8000/v2/myorg/myrepo/blobs/uploads'

req.method
# 'POST'
```

And do the request. You should get back a 202 response with a "Location" header.

```python
response = client.Do(req)
```
```
response
# <Response [202]>

response.headers['Location']
# '/v2/put/1/session-942e656f-d08f-4df9-a9e4-575eb59aae77/blobs/upload/'
```

Note that you'll have about 10 minutes for this URL to be valid, which is one
of the settings you can configure for your registry.
You also actually don't need to worry about knowing the Location header, because it will be provided
to the Reggie client with the GetRelativeLocation() function provided with the response object.
Next, let's upload our image blob! First, we need a digest. Here is a function to calculate one:

```python
import hashlib
def calculate_digest(blob):
    """Given a blob (the body of a response) calculate the sha256 digest"""
    hasher = hashlib.sha256()
    hasher.update(blob)
    return "sha256:%s" % hasher.hexdigest()
```

And here we can do it:

```python
# Read binary data and calculate sha256 digest
with open(image, "rb") as fd:
    data = fd.read()
digest = calculate_digest(data)
# sha256:bdebf360662e987574743eeb862950e5d6ac15fbb90150de7ac8f3af02834c7a
```

Next, let's upload the blob.

```python
req = (client.NewRequest("PUT", response.GetRelativeLocation()).
        SetHeader("Content-Type", "application/octet-stream").
        SetHeader("Content-Length", str(len(data))).
        SetQueryParam("digest", digest).
        SetBody(data)
      )
blobResponse = client.Do(req)
# <Response [201]>
```

You'll again have a Location header, but this time, you get back a url to pull the blob.

```python
blobResponse.headers['Location']
http://127.0.0.1:8000/v2/myorg/myrepo/blobs/sha256:bdebf360662e987574743eeb862950e5d6ac15fbb90150de7ac8f3af02834c7a/
```

Let's test doing that!

```python
req = client.NewRequest("GET", blobResponse.GetRelativeLocation())
downloadResponse = client.Do(req)
# <Response [200]>
```

#### 4. Chunked upload of a blob

This time, we want to do a chunked upload. We'll need to essentially break our binary into pieces
and upload in chunks. First, let's write a function to split it into chunks and yield each one:

```python
def read_in_chunks(image, chunk_size=1024):
    """Helper function to read file in chunks, with default size 1k."""
    while True:
        data = image.read(chunk_size)
        if not data:
            break
        yield data
```

And again prepare the request. This time, we provide a content length of 0 and no digest.

```python
req = (client.NewRequest("POST", "/v2/<name>/blobs/uploads").
        SetHeader("Content-Type", "application/octet-stream").
        SetHeader("Content-Length", "0"))
response = client.Do(req)
# <Response [202]>
```

And again, now let's use the Location header to upload our blob, but this time in
a chunked fashion.

```python
# Read the file in chunks, for each do a patch
start = 0
with open(image, "rb") as fd:
    for chunk in read_in_chunks(fd):
        if not chunk:
            break

        end = start + len(chunk) - 1
        content_range = "%s-%s" % (start, end)

        # Prepare the request
        req = (client.NewRequest("PATCH", response.GetRelativeLocation()).
            SetHeader("Content-Type", "application/octet-stream").
            SetHeader("Content-Length", str(len(chunk))).
            SetHeader("Content-Range", content_range).
            SetBody(chunk))
        start = end + 1
        chunkResponse = client.Do(req)
```

If you are watching your registry output, you should see a bunch of 202 responses
for each chunk.

```
...
[19/Oct/2020 19:20:36] "PATCH /v2/put/2/session-1af6f518-9156-4a9c-ac23-5505e67ed4f7/blobs/upload HTTP/1.1" 202 0
[19/Oct/2020 19:20:36] "PATCH /v2/put/2/session-1af6f518-9156-4a9c-ac23-5505e67ed4f7/blobs/upload HTTP/1.1" 202 0
```

Finally, let's issue a PUT request to finish the blob

```python
req = (client.NewRequest("PUT",  response.GetRelativeLocation()).
        SetQueryParam("digest", digest))
putResponse = client.Do(req)
# <Response [201]>
```

We can again see the download url in the Location header.

```python
putResponse.GetAbsoluteLocation()
'http://127.0.0.1:8000/v2/myorg/myrepo/blobs/sha256:bdebf360662e987574743eeb862950e5d6ac15fbb90150de7ac8f3af02834c7a/'

putResponse.GetRelativeLocation()
'/v2/myorg/myrepo/blobs/sha256:bdebf360662e987574743eeb862950e5d6ac15fbb90150de7ac8f3af02834c7a/'
```

#### 5. Upload a manifest

Let's pretend that we just uploaded a manifest config blob, and we'll use it to create
a manifest with no layers (this is all kinds of wrong, but will work for the example).
For an actual use case, you would upload a config blob, and then one or more layer blobs,
and put them together to form the manifest. Here we will pretend that the same blob is both a layer
and a config blob. :)

```python
manifest = {
  "schemaVersion": 2,
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "size": len(data),
    "digest": digest
  },
  "layers": [ {
    "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
    "size": len(data),
    "digest": digest,
   }]
}
```

We can validate the manifest.

```python
from opencontainers.image.v1 import Manifest
m = Manifest()
m.load(manifest)
```

Now prepare and issue the request to upload the manifest. Notice that we are adding a tag
reference "latest":

```python
req = (client.NewRequest("PUT", "/v2/<name>/manifests/<reference>",
     WithReference("latest")).
     SetHeader("Content-Type", "application/vnd.oci.image.manifest.v1+json").
     SetBody(manifest))
response = client.Do(req)
```

We should see a 201 response!

```python
# <Response [201]>
```

Now we can validate the uploaded content. We are changing PUT to GET.

```python
req = (client.NewRequest("GET", "/v2/<name>/manifests/<reference>",
        WithReference("latest")).
        SetHeader("Accept", "application/vnd.oci.image.manifest.v1+json"))
response = client.Do(req)
```
```python
response.json()
{'schemaVersion': 2,
 'config': {'mediaType': 'application/vnd.oci.image.config.v1+json',
  'size': 786432,
  'digest': 'sha256:bdebf360662e987574743eeb862950e5d6ac15fbb90150de7ac8f3af02834c7a'},
 'layers': [{'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip',
   'size': 786432,
   'digest': 'sha256:bdebf360662e987574743eeb862950e5d6ac15fbb90150de7ac8f3af02834c7a'}]}
```


#### 6. List Tags

Let's list the tag we just uploaded!

```python
req = client.NewRequest("GET", "/v2/<name>/tags/list")

req.url
# 'http://127.0.0.1:8000/v2/myorg/myrepo/tags/list'
```

Remember that you could change the name of the repository on the fly:

```python
req = (client.NewRequest("GET", "/v2/<name>/tags/list",
    WithName("vsoch/django-oci")))

req.url
# 'http://127.0.0.1:8000/v2/vsoch/django-oci/tags/list'

req.method
# 'GET'
```

Let's do the request!

```python
response = client.Do(req)
```

We get the tags!
```
response
# <Response [200]>

response.json()
# {'name': 'myorg/myrepo', 'tags': ['latest']}
```

We should be adding documentation for authentication after it's implemented.
In the meantime, if you have a question or want to contribute, please [let us know]({{ site.repo}}/issues).
