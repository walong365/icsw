# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

""" DB definitions for background jobs """

from django.db import models
import logging
import server_command

logger = logging.getLogger(__name__)

__all__ = [
    "background_job",
    "background_job_run",
]


class background_job(models.Model):
    idx = models.AutoField(primary_key=True)
    # cause
    cause = models.CharField(max_length=256, default="unknown")
    # command as text
    command = models.CharField(null=False, max_length=256)
    # state
    state = models.CharField(
        max_length=128, default="pre-init",
        choices=[
            ("pre-init", "before cluster-server detection"),
            ("pending", "init and awaiting processing"),
            ("done", "job finished"),
            ("timeout", "timeout"),
            ("merged", "merged with other job"),
        ]
    )
    # command as XML
    command_xml = models.TextField(null=False)
    # initiator
    initiator = models.ForeignKey("backbone.device", related_name="bgj_initiator")
    # server to run on
    target_server = models.ForeignKey("backbone.device", null=True, related_name="bgj_target_server")
    # creator, mostly null due to problem with thread local storage
    user = models.ForeignKey("backbone.user", null=True, on_delete=models.SET_NULL)
    # created
    date = models.DateTimeField(auto_now_add=True)
    # valid until
    valid_until = models.DateTimeField(null=True)
    # number of servers to contact
    num_servers = models.IntegerField(default=0)

    class Meta:
        ordering = ("-date",)
        app_label = "backbone"
        verbose_name = "Background jobs"


class background_job_run(models.Model):
    idx = models.AutoField(primary_key=True)
    # background job
    background_job = models.ForeignKey("backbone.background_job")
    # where the job was run
    server = models.ForeignKey("backbone.device")
    # log source, old style
    log_source = models.ForeignKey("backbone.log_source", null=True, default=None)
    # log source, new style
    source = models.ForeignKey("backbone.LogSource", null=True, default=None)
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
        verbose_name = "Background job run"
