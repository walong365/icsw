"""
Provides model fields that don't have an equivalent in Django.
"""

from django.db import models

from initat.core.alfresco.storage import AlfrescoStorage


class AlfrescoFileField(models.FileField):
    def __init__(self, directory, **kwargs):
        # Remove storage and set to AlfrescoStorage if somebody passes
        # it in
        kwargs.pop("storage", None)
        super(AlfrescoFileField, self).__init__(storage=AlfrescoStorage(directory=directory), **kwargs)
