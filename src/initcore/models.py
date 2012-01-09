import base64
import marshal

from django.db import models
from django.contrib.auth.models import User

class user_variable(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey(User)
    name = models.CharField(max_length=64)
    # new model
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
