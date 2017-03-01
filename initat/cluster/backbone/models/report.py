#
# Copyright (C) 2016-2017 Gregor Kaufmann, Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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


import os
import base64
import hashlib

from django.db import models

from rest_framework import serializers

from initat.cluster.settings import REPORT_DATA_STORAGE_DIR

########################################################################################################################
# (Django Database) Classes
########################################################################################################################

FILENAME_DATE_STRING = "%Y_%m_%d"   # _%H_%M_%S"
HASH_ALGORITHM = "sha256"


class ReportHistory(models.Model):
    idx = models.AutoField(primary_key=True)
    created_by_user = models.ForeignKey("backbone.user", null=True)
    created_at_time = models.DateTimeField(null=True)
    number_of_pages = models.IntegerField(default=0)
    number_of_downloads = models.IntegerField(default=0)
    size = models.BigIntegerField(default=0)
    b64_size = models.BigIntegerField(default=0)
    type = models.TextField(null=True)
    filename = models.TextField(null=True)
    progress = models.IntegerField(default=0)
    file_hash = models.TextField(null=True)
    hash_algorithm = models.TextField(null=True)

    def write_data(self, data):
        b64data = base64.b64encode(data)
        self.b64_size = len(b64data)

        hash_algo = getattr(hashlib, HASH_ALGORITHM)()
        hash_algo.update(data)
        self.file_hash = hash_algo.hexdigest()
        self.hash_algorithm = HASH_ALGORITHM

        path = self._data_storage_path
        try:
            os.makedirs(os.path.dirname(path))
        except OSError:
            pass
        with open(self._data_storage_path, "wb") as file_:
            file_.write(data)

    def get_data(self):
        with open(self._data_storage_path, "rb") as file_:
            data = file_.read()
            return data

    @property
    def _data_storage_path(self):
        return os.path.join(
            REPORT_DATA_STORAGE_DIR,
            self.file_hash[0],
            self.file_hash[1],
            self.file_hash,
        )

    @property
    def _full_filename_path(self):
        return os.path.join(self._data_storage_path, self.filename)

    def generate_filename(self):
        file_ending = "pdf" if self.type == "pdf" else "zip"

        self.filename = "Report_{}_{}.{}".format(
            self.idx,
            self.created_at_time.strftime(FILENAME_DATE_STRING),
            file_ending
        )

    def delete_storage_file(self):
        try:
            os.remove(self._full_filename_path)
        except Exception as e:
            _ = e


########################################################################################################################
# Serializers
########################################################################################################################


class ReportHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportHistory
        fields = (
            "idx", "created_by_user", "created_at_time", "number_of_pages", "number_of_downloads"
        )
