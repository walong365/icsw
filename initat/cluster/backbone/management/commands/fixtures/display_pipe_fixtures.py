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



import json

from initat.cluster.backbone import factories
from initat.cluster.backbone.models import SPECIAL_USER_VAR_NAMES


def add_fixtures(**kwargs):
    for _name, _description, _uvn, _sys_pipe, _spec in [
        (
            "testview",
            "Simple Pipe for testing",
            SPECIAL_USER_VAR_NAMES.livestatus_dashboard_pipe.value,
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
        (
            "networktopology",
            "Pipe for network Topology",
            SPECIAL_USER_VAR_NAMES.network_topology_pipe.value,
            True,
            json.dumps(
                {
                    "icswLivestatusSelDevices": [{
                        "icswLivestatusDataSource": [{
                            "icswLivestatusFilterService": [{
                                "icswLivestatusTopologySelector": [{
                                    "icswLivestatusFilterService": [{
                                        "icswLivestatusNetworkTopology": []
                                    }]
                                },
                                {
                                    "icswLivestatusNetworkTopology": []
                                }]
                            }]
                        }]
                    }]
                }
            )
        ),
        (
            "devicelocation",
            "Pipe for device location",
            SPECIAL_USER_VAR_NAMES.device_location_pipe.value,
            True,
            json.dumps(
                {
                    "icswLivestatusSelDevices": [{
                        "icswLivestatusDataSource": [{
                            "icswLivestatusFilterService": [{
                                "icswLivestatusMonCategoryFilter": [{
                                    "icswLivestatusDeviceCategoryFilter": [{
                                        "icswLivestatusGeoLocationDisplay": []
                                    },
                                    {
                                        "icswLivestatusLocationMap": []
                                    }]
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
            def_user_var_name=_uvn,
            public_pipe=True,
            json_spec=_spec,
        )
