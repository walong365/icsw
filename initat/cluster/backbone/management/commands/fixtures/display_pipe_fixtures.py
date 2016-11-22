# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for display pipes """

from __future__ import unicode_literals, print_function

import json
from django.conf import settings
from django.db.models import Q

from initat.cluster.backbone import factories
from initat.tools import logging_tools


def add_fixtures(**kwargs):
    for _name, _description, _sys_pipe, _spec in [
        (
            "testview",
            "Simple Pipe for testing",
            True,
            json.dumps(
                {
                    "icswLivestatusSelDevices": [{
                        "icswLivestatusDataSource": [{
                            "icswLivestatusFilterService": [{
                                "icswLivestatusMonCategoryFilter": [{
                                    "icswLivestatusDeviceCategoryFilter": [
                                        {
                                            "icswLivestatusMonTabularDisplay": []
                                        },
                                        {
                                            "icswLivestatusDeviceTabularDisplay": []
                                        },
                                        {
                                            "icswLivestatusInfoDisplay": []
                                        }
                                    ]
                                }]
                            }]
                        }]
                    }]
                }
            )
        ),
    ]:
        factories.MonDisplayPipeSpecFactory(
            name=_name,
            description=_description,
            system_pipe=_sys_pipe,
            public_pipe=True,
            json_spec=_spec,
        )
