# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

angular.module(

    # livestatus helper functions

    "icsw.backend.livestatus",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.user",
    ]
).service("icswLivestatusPipeSpecTree",
[
    "$q",
(
    $q,
) ->
    class icswLivestatusPipeSpecTree
        constructor: (list) ->
            @list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @lut = _.keyBy(@list, "idx")
            @name_lut = _.keyBy(@list, "name")

        spec_name_defined: (name) =>
            return if name of @name_lut then true else false

]).service("icswLivestatusPipeSpecTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTreeBase",
    "icswTools", "icswLivestatusPipeSpecTree",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTreeBase,
    icswTools, icswLivestatusPipeSpecTree,
) ->
    rest_map = [
        ICSW_URLS.REST_MON_DISPLAY_PIPE_SPEC_LIST
    ]
    return new icswTreeBase(
        "DeviceLivestatusPipeSpecTree"
        icswLivestatusPipeSpecTree
        rest_map
        ""
    )
])
