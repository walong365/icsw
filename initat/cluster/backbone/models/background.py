# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

from __future__ import unicode_literals, print_function

import logging

from enum import Enum

from django.db import models

from initat.tools import server_command

logger = logging.getLogger(__name__)

__all__ = [
    b"background_job",
    b"background_job_run",
    b"BackgroundJobState",
]


class BackgroundJobState(Enum):
    # not handled, ready for pick-up by cluster server
    pre_init = "pre-init"
    # timeout
    timeout = "timeout"
    # finished
    done = "done"
    # used for running, waiting for completion
    pending = "pending"
    # merged ???
    merged = "merged"


class background_job(models.Model):
    idx = models.AutoField(primary_key=True)
    # cause
    cause = models.CharField(max_length=256, default="unknown")
    # command as text
    command = models.CharField(null=False, max_length=256)
    # options as text
    options = models.CharField(default="", max_length=256)
    # state
    state = models.CharField(
        max_length=128,
        default=BackgroundJobState.pre_init.value,
        choices=[
            (BackgroundJobState.pre_init.value, "before cluster-server detection"),
            (BackgroundJobState.pending.value, "init and awaiting processing"),
            (BackgroundJobState.done.value, "job finished"),
            (BackgroundJobState.timeout.value, "timeout"),
            (BackgroundJobState.merged.value, "merged with other job"),
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
    # number of objects, defaults to 0
    num_objects = models.IntegerField(default=0)
    # result, is server_REPLY
    result = models.IntegerField(default=server_command.SRV_REPLY_STATE_UNSET)

    def __unicode__(self):
        return "background_job {:d}".format(self.idx)

    def initiator_name(self):
        return self.initiator.full_name

    def user_name(self):
        return unicode(self.user) if self.user_id else "---"

    def set_state(self, state, result=None):
        self.state = state.value
        if state in [BackgroundJobState.timeout]:
            self.result = server_command.SRV_REPLY_STATE_ERROR
        elif state in [BackgroundJobState.done]:
            self.result = server_command.SRV_REPLY_STATE_OK
        elif state in [BackgroundJobState.pending]:
            self.result = server_command.SRV_REPLY_STATE_WARN
        if result is not None:
            # override automatic decision
            self.result = result
        self.save()

    class Meta:
        ordering = ("-date",)
        verbose_name = "Background jobs"

    class CSW_Meta:
        permissions = (
            ("show_background", "Show background jobs", False),
        )


class background_job_run(models.Model):
    idx = models.AutoField(primary_key=True)
    # background job
    background_job = models.ForeignKey("backbone.background_job")
    # where the job was run
    server = models.ForeignKey("backbone.device")
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
        verbose_name = "Background job run"
