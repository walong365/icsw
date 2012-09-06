"""
Just one basic model to save general user preferences
in a key: value fashion.
"""

import base64
import marshal
from django.db import models
from django.contrib.auth.models import User


class AlfrescoDocument(models.Model):
    """
    The model for *all* Alfresco documents.
    """
    uuid = models.CharField(max_length=36, primary_key=True)
    version_major = models.IntegerField()
    version_minor = models.IntegerField()
    path = models.TextField()
    upload_date = models.DateTimeField()

    class Meta:
        app_label = u'edmdb'


class user_variable(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey(User)
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
