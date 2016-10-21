# -*- coding: utf-8 -*-
#
# Copyright (C) 016 Andreas Lang-Nevyjel
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

""" Serializers for license related objects (ova) """

from __future__ import unicode_literals, print_function

import logging

from rest_framework import serializers

from initat.cluster.backbone.models import icswEggCradle, icswEggBasket

logger = logging.getLogger(__name__)

__all__ = [
    b"icswEggBasketSerializer",
    b"icswEggCradleSerializer",
]


class icswEggBasketSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = icswEggBasket


class icswEggCradleSerializer(serializers.ModelSerializer):
    icsweggbaset_set = icswEggBasketSerializer(read_only=True, many=True)

    class Meta:
        fields = "__all__"
        model = icswEggCradle
