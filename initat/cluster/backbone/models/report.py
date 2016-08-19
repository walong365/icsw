#
# Copyright (C) 2016 Gregor Kaufmann, Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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

from django.db import models

from rest_framework import serializers

########################################################################################################################
# (Django Database) Classes
########################################################################################################################

class ReportHistory(models.Model):
    idx = models.AutoField(primary_key=True)

    created_by_user = models.ForeignKey("backbone.user", null=True)

    created_at_time = models.DateTimeField(null=True)

    number_of_pages = models.IntegerField(default=0)

    number_of_downloads = models.IntegerField(default=0)

    data = models.TextField(null=True)

########################################################################################################################
# Serializers
########################################################################################################################

class ReportHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportHistory
        fields = (
            "idx", "created_by_user", "created_at_time", "number_of_pages", "number_of_downloads"
        )