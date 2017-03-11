# Copyright (C) 2012-2017 init.at
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
    "icsw.weathermap",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "restangular",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.weathermap")
]).service("icswWeathermapEntry",
[
    "$q",
(
    $q,
) ->
    class icswWeathermapEntry
        constructor: (dev, wm_type, db_obj, data) ->
            @device = dev
            @wm_type = wm_type
            @db_obj = db_obj
            @data = data
            @_salt()
            @_set_values()
            @$$filter_field = "#{@device.$$print_name} #{@wm_type} #{@$$display_value} #{@spec}"

        _salt: () ->
            if @wm_type == "network"
                @spec = @db_obj.devname
            else
                @spec = ""

        _set_values: () ->
            _parsed = @data[".parsed"]
            @$$cmp_value = _parsed.cmp_value
            @$$display_value = ("#{v} #{k}" for k, v of _parsed.display).join(", ")

]).controller("icswWeathermapOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "$uibModal", "$timeout", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswParseXMLResponseService", "toaster", "icswUserService", "icswGraphTools",
    "icswDeviceTreeHelperService", "icswDeviceTreeService", "icswWeathermapEntry",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $uibModal, $timeout, ICSW_URLS, icswSimpleAjaxCall,
    icswParseXMLResponseService, toaster, icswUserService, icswGraphTools,
    icswDeviceTreeHelperService, icswDeviceTreeService, icswWeathermapEntry,
) ->
    $scope.struct = {
        # device tree
        device_tree: undefined
        # loading
        loading: true
        # data valid
        data_valid: false
        # devices
        devices: []
        # wm entries, one per type
        wm_entries: {
            memory: []
            load: []
            network: []
        }
        # reload timeout
        rl_timeout: undefined
    }
    _build_wm_entries = (result) ->
        dev_lut = _.keyBy($scope.struct.devices, "uuid")
        for key, value of $scope.struct.wm_entries
            value.length = 0
        for uuid, uuid_s of result
            dev = dev_lut[uuid]
            for wm_type, s_dict of uuid_s
                if wm_type == "load"
                    new_wme = new icswWeathermapEntry(
                        dev
                        wm_type
                        ""
                        s_dict
                    )
                    $scope.struct.wm_entries[wm_type].push(new_wme)
                else if wm_type == "memory"
                    new_wme = new icswWeathermapEntry(
                        dev
                        wm_type
                        ""
                        s_dict
                    )
                    $scope.struct.wm_entries[wm_type].push(new_wme)
                else
                    #
                    for nd_idx, nd_data of s_dict
                        if nd_idx of dev.netdevice_lut
                            new_wme = new icswWeathermapEntry(
                                dev
                                wm_type
                                dev.netdevice_lut[nd_idx]
                                nd_data
                            )
                            $scope.struct.wm_entries[wm_type].push(new_wme)


    _stop_reload = () ->
        if $scope.struct.rl_timeout?
            $timeout.cancel($scope.struct.rl_timeout)
        $scope.struct.rl_timeout = undefined

    _start_reload = () ->
        _stop_reload()
        icswSimpleAjaxCall(
            url: ICSW_URLS.DEVICE_GET_WEATHERMAP_DATA
            dataType: "json"
            data:
                device_idxs: angular.toJson((dev.idx for dev in $scope.struct.devices))
        ).then(
            (result) ->
                $scope.struct.loading = false
                $scope.struct.data_valid = true
                _build_wm_entries(result)
                $scope.struct.rl_timeout = $timeout(
                    () ->
                        $scope.struct.rl_timeout = undefined
                        _start_reload()
                    5000
                )
        )

    $scope.new_devsel = (dev_list) ->
        $scope.struct.devices.length = 0
        for dev in dev_list
            if not dev.is_meta_device
                $scope.struct.devices.push(dev)
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, $scope.struct.devices)
                $scope.struct.device_tree.enrich_devices(hs, ["network_info"]).then(
                    (done) ->
                        _start_reload()
                )
        )

    $scope.$on("$destroy", () ->
        _stop_reload()
    )
]).directive("icswWeathermapOverview",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile,
) ->
    return {
        restrict: "E"
        template: $templateCache.get("icsw.weathermap.overview")
        controller: "icswWeathermapOverviewCtrl"
    }
])
