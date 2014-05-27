#!/usr/bin/python-init

from django.db import models
from rest_framework import serializers
import logging
import server_command

logger = logging.getLogger(__name__)

__all__ = [
    "background_job", "background_job_serializer",
    "background_job_run", "background_job_run_serializer",
    ]

class background_job(models.Model):
    idx = models.AutoField(primary_key=True)
    # cause
    cause = models.CharField(max_length=256, default="unknown")
    # command as text
    command = models.CharField(null=False, max_length=256)
    # state
    state = models.CharField(max_length=128, default="pre-init", choices=[
        ("pre-init", "before cluster-server detection"),
        ("pending", "init and awaiting processing"),
        ("done", "job finished"),
        ("timeout", "timeout"),
        ("merged", "merged with other job"),
        ])
    # command as XML
    command_xml = models.TextField(null=False)
    # initiator
    initiator = models.ForeignKey("backbone.device", related_name="bgj_initiator")
    # server to run on
    target_server = models.ForeignKey("backbone.device", null=True, related_name="bgj_target_server")
    # creator, mostly null due to problem with thread local storage
    user = models.ForeignKey("backbone.user", null=True)
    # created
    date = models.DateTimeField(auto_now_add=True)
    # valid until
    valid_until = models.DateTimeField(null=True)
    # number of servers to contact
    num_servers = models.IntegerField(default=0)
    def __unicode__(self):
        return "background_job {:d}".format(self.idx)
    class Meta:
        ordering = ("-date",)
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
    log_source = models.ForeignKey("backbone.log_source", null=True, default=None)
    # command as XML
    command_xml = models.TextField(null=False)
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

class background_job_run_serializer(serializers.ModelSerializer):
    class Meta:
        model = background_job_run
