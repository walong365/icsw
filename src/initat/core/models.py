# -*- coding: utf-8 -*-

import base64
import datetime
import marshal
from django.conf import settings
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User


class AbstractAlfrescoDocument(models.Model):
    """
    A handy abstract model from Alfresco documents.
    """
    uuid = models.CharField(max_length=36, primary_key=True)
    version_major = models.IntegerField()
    version_minor = models.IntegerField()
    path = models.TextField()
    upload_date = models.DateTimeField()

    class Meta:
        abstract = True


class AlfrescoDocument(AbstractAlfrescoDocument):
    """
    This is the model that AlfrescoFileFields use.
    """
    pass


class user_variable(models.Model):
    """
    Stores arbitrary name value combinations per user.
    """
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="core_variable")
    name = models.CharField(max_length=64)
    value_0 = models.TextField(null=False, default="")

    def store(self, value, **kwargs):
        self.value_0 = base64.b64encode(marshal.dumps(value))
        if kwargs.get("no_store", True):
            self.save()

    def load(self):
        return marshal.loads(base64.b64decode(self.value_0))

    def __unicode__(self):
        return "%s for %s: %d bytes" % (self.name,
                                        self.user,
                                        len(self.value_0))


@receiver(pre_save, sender=AlfrescoDocument)
def _alf_document_pre_save(sender, instance, raw, using, **kwargs):
    instance.upload_date = datetime.datetime.now()
