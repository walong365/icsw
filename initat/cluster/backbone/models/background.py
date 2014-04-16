#!/usr/bin/python-init

from django.db import models
from rest_framework import serializers
import logging
import server_command

logger = logging.getLogger(__name__)

__all__ = [
    "background_job", "background_job_serializer",
    ]

class background_job(models.Model):
    idx = models.AutoField(primary_key=True)
    # command as text
    command = models.CharField(null=False, max_length=256)
    # command as XML
    command_xml = models.TextField(null=False)
    # server to run on
    target_server = models.ForeignKey("backbone.device", null=True)
    # creator, mostly null due to problem with thread local storage
    user = models.ForeignKey("backbone.user", null=True)
    # created
    date = models.DateTimeField(auto_now_add=True)
    # valid until
    valid_until = models.DateTimeField(null=True)
    # number of servers
    num_servers = models.IntegerField(default=0)
    def __unicode__(self):
        return "bg_job_{:d}".format(self.idx)
    class Meta:
        ordering = ("date",)
        app_label = "backbone"
    class CSW_Meta:
        permissions = (
            ("show_background", "Show background jobs", False),
        )

class background_job_serializer(serializers.ModelSerializer):
    class Meta:
        model = background_job

class background_job_run(models.Model):
    idx = models.AutoField(primary_key=True)
    # background job
    background_job = models.ForeignKey("backbone.background_job")
    # where the job was run
    server = models.ForeignKey("backbone.device")
    # log source
    log_source = models.ForeignKey("backbone.log_source")
    # result
    state = models.IntegerField(default=server_command.SRV_REPLY_STATE_UNSET)
    result = models.TextField(default="")
    result_xml = models.TextField(null=True)
    # run time info
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    # created
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ("date",)
        app_label = "backbone"

class background_job_ignore(models.Model):
    idx = models.AutoField(primary_key=True)
    # background job
    background_job = models.ForeignKey("backbone.background_job")
    # where the job was run
    server = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ("date",)
        app_label = "backbone"

class background_job_run_serializer(serializers.ModelSerializer):
    class Meta:
        model = background_job_run

class background_job_ignore_serializer(serializers.ModelSerializer):
    class Meta:
        model = background_job_ignore

