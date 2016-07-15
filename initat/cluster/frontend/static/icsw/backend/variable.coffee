# Copyright (C) 2012-2016 init.at
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

angular.module(

    # device tree handling (including device enrichment)

    "icsw.backend.variable",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.user",
    ]
).service("icswDeviceVariableScopeTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswEnrichmentInfo",
    "icswSimpleAjaxCall", "$rootScope", "$timeout", "icswDeviceTreeGraph",
    "ICSW_SIGNALS", "icswDeviceTreeHelper", "icswNetworkTreeService",
(
    icswTools, ICSW_URLS, $q, Restangular, icswEnrichmentInfo,
    icswSimpleAjaxCall, $rootScope, $timeout, icswDeviceTreeGraph,
    ICSW_SIGNALS, icswDeviceTreeHelper, icswNetworkTreeService
) ->
    class icswDeviceVariableScopeTree
        constructor: (list) ->
            @list = []
            @update(list)
            
        update: (list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @build_luts()
            
        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
]).service("icswDeviceVariableScopeTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTreeBase",
    "icswTools", "icswDeviceVariableScopeTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTreeBase,
    icswTools, icswDeviceVariableScopeTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        ICSW_URLS.DEVICE_DEVICE_VARIABLE_SCOPE_LIST
    ]
    return new icswTreeBase(
        "DeviceVariableScopeTree"
        icswDeviceVariableScopeTree
        rest_map
        ""
    )
])
