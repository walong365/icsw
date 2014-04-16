#!/usr/bin/python-init

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_integer
from lxml.builder import E # @UnresolvedImport
from rest_framework import serializers
import logging
import logging_tools
import re
import server_command

logger = logging.getLogger(__name__)

__all__ = [
    "background_job", "background_job_serializer",
    ]

class background_job(models.Model):
    idx = models.AutoField(primary_key=True)
    # command as XML
    command = models.TextField(null=False)
    # result
    state = models.IntegerField(default=server_command.SRV_REPLY_STATE_UNSET)
    result = models.TextField(default="")
    # pending
    pending = models.BooleanField(default=True)
    # server to run on
    target_server = models.ForeignKey("backbone.device", null=True)
    # creator
    user = models.ForeignKey("backbone.user", null=True)
    # created
    date = models.DateTimeField(auto_now_add=True)
    # started
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    # valid until
    valid_until = models.DateTimeField(null=True)
    def __unicode__(self):
        return "bg_job_{:d}".format(self.idx)
    class Meta:
        ordering = ("date",)

class background_job_serializer(serializers.ModelSerializer):
    class Meta:
        model = background_job
