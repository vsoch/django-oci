"""

Copyright (c) 2020, Vanessa Sochat

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Image

@receiver(post_delete, sender=Image)
def delete_blobs(sender, instance, **kwargs):
    print("Delete image signal running.")

    # Check for blobs
    if instance.image not in ["", None]:
        if hasattr(instance.image, "datafile"):
            count = Container.objects.filter(
                image__datafile=instance.image.datafile
            ).count()
            if count == 0:
                print("Deleting %s, no longer used." % instance.image.datafile)
                instance.image.datafile.delete()
