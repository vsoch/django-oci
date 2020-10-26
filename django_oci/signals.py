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
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import Image
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model

UserModel = get_user_model()


@receiver(post_delete, sender=Image)
def delete_blobs(sender, instance, **kwargs):
    print("Delete image signal running.")

    for blob in instance.blobs.all():
        if hasattr(blob, "datafile"):
            if blob.image_set.count() == 0:
                print("Deleting %s, no longer used." % blob.datafile)
                blob.datafile.delete()
                blob.delete()


@receiver(post_save, sender=UserModel)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    """Create a token for the user when the user is created (with oAuth2)

    1. Assign user a token
    2. Assign user to default group

    Create a Profile instance for all newly created User instances. We only
    run on user creation to avoid having to check for existence on each call
    to User.save.
    """
    if created:
        Token.objects.create(user=instance)
