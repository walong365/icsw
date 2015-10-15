# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

monitoring_device_module = angular.module(
    "icsw.monitoring.device",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"
    ]
).directive('icswMonitoringDevice', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.monitoring.device"
    }
]).service('icswMonitoringDeviceService', ["ICSW_URLS", "Restangular", "msgbus", "icswSimpleAjaxCall", (ICSW_URLS, Restangular, msgbus, icswSimpleAjaxCall) ->
    get_rest = (url, opts={}) -> return Restangular.all(url).getList(opts).$object
    data = {
        mon_device_templ   : get_rest(ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST.slice(1))
        mon_ext_host       : get_rest(ICSW_URLS.REST_MON_EXT_HOST_LIST.slice(1))
        mon_server         : get_rest(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1), {"monitor_server_type" : true})
    }

    ret = {
        rest_url            : ICSW_URLS.REST_DEVICE_TREE_LIST
        rest_options        : {"ignore_meta_devices" : true, "olp" : "backbone.device.change_monitoring"}
        edit_template       : "device.monitoring.form"
        md_cache_modes : [
            {"idx" : 1, "name" : "automatic (server)"}
            {"idx" : 2, "name" : "never use cache"}
            {"idx" : 3, "name" : "once (until successful)"}
        ]
        init_fn: ($scope) ->
            msgbus.emit("devselreceiver")
            msgbus.receive("devicelist", $scope, (name, args) ->
                $scope.reload(args[1])
            )
        fetch : (edit_obj) ->
            # $.blockUI()
            icswSimpleAjaxCall(
                url     : ICSW_URLS.MON_FETCH_PARTITION
                data    :
                    "pk" : edit_obj.idx
            ).then((xml) ->
            )
    }
    for k, v of data  # shallow copy
        ret[k] = v
    return ret
])
