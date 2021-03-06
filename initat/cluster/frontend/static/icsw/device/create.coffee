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
    "icsw.device.create",
    [
        "ngSanitize", "ui.bootstrap", "restangular"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.devicecreate")
]).directive("icswDeviceCreateMask",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.create.mask")
        controller: "icswDeviceCreateCtrl"
        scope: {
            device_info: '=deviceinfo'
        }
    }
]).controller("icswDeviceCreateCtrl",
[
    "$scope", "$timeout", "$window", "$templateCache", "$q", "blockUI", "ICSW_URLS", "ICSW_SIGNALS",
    "icswSimpleAjaxCall", "Restangular", "$state", "$stateParams", "icswActiveSelectionService",
    "icswDeviceTreeService", "icswPeerInformationService", "DeviceOverviewService",
(
    $scope, $timeout, $window, $templateCache, $q, blockUI, ICSW_URLS, ICSW_SIGNALS,
    icswSimpleAjaxCall, Restangular, $state, $stateParams, icswActiveSelectionService,
    icswDeviceTreeService, icswPeerInformationService, DeviceOverviewService,
) ->

    # console.log($scope.device_info)

    $scope.struct = {
        # device tree
        device_tree: undefined
        # peer tree
        peer_tree: undefined
        # data ready
        data_ready: false
        # resolve pending
        resolve_pending: false
        # base is open
        base_open: true
        # any images found
        any_images_found: false
        # image url
        img_url: ""
        # ip is fixed (was entered manually)
        ip_fixed: false
        # matching names
        matching_names_found: 0
        matching_names: []
        # same search is pending
        same_seach_pending: false
        # device selection
        dev_sel_list: [
            {key: "keep", value: "keep current Selection"}
            {key: "add", value: "add to current Selection"}
            {key: "replace", value: "replace current Selection"}
        ]
        bulk_create_mode: false
        bulk_create_current_device: undefined
        bulk_create_total_devices: undefined
    }

    $scope.device_data = {
        # localhost would be plane stupid
        full_name: ""
        comment: "new device, created at " + moment().format()
        device_group: "newgroup"
        ip: ""
        resolve_via_ip: true
        routing_capable: false
        peer: 0
        icon_name: "linux40"
        dev_selection: $scope.struct.dev_sel_list[0]
        mac: "00:00:00:00:00:00"
        nmap_device: undefined
    }

    if $scope.device_info != undefined
        $scope.struct.bulk_create_mode = true
        $scope.struct.bulk_create_current_device = 0
        $scope.struct.bulk_create_total_devices = $scope.device_info.length

        $scope.skip_device = () ->
            init_with_device_info()

    init_with_device_info = () ->
        if $scope.device_info != undefined
            if $scope.device_info.length > 0
                next_device = $scope.device_info[0]
                $scope.device_data.nmap_device = next_device
                $scope.device_info = _.drop($scope.device_info)

                $scope.struct.bulk_create_current_device += 1

                if next_device.hostname != null
                    $scope.device_data.full_name = next_device.hostname
                $scope.device_data.ip = next_device.ip
                $scope.device_data.mac = next_device.$$mac
            else
                $scope.device_info = undefined
                init_with_device_info()
        else
            $scope.device_data.full_name = ""
            $scope.device_data.ip = ""
            $scope.device_data.mac = "00:00:00:00:00:00"
            $scope.device_data.nmap_device = undefined
            $scope.struct.bulk_create_mode = false

    init_with_device_info()

    $scope.on_icon_select = (item, model, label) ->
        $scope.struct.img_url = item.data_image
        $scope.device_data.icon_name = item.name

    $scope.get_group_names = (search) ->
        new_groups = (group.name for group in $scope.struct.device_tree.group_list)
        if (search && new_groups.indexOf(search) == -1)
            new_groups.unshift(search)

        return new_groups

    $scope.reload = () ->
        blockUI.start("Fetching Data from Server ...")
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswPeerInformationService.load($scope.$id, [])
                Restangular.all(ICSW_URLS.REST_MON_EXT_HOST_LIST.slice(1)).getList()
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.peer_tree = data[1]
                $scope.struct.mon_ext_host = data[2]
                if $scope.struct.mon_ext_host.length
                    $scope.struct.any_images_found = true
                    _match = (entry for entry in $scope.struct.mon_ext_host when entry.name == $scope.device_data.icon_name)
                    if _match.length
                        _first = _match[0]
                    else if $scope.struct.mon_ext_host.length
                        _first = $scope.struct.mon_ext_host[0]
                    else
                        _first = null
                    if _first
                        $scope.struct.img_url = _first.data_image
                        $scope.device_data.icon_name = _first.name
                    else
                        # nothing found
                        $scope.struct.img_url = ""
                        $scope.device_data.icon_name = ""
                else
                    $scope.struct.any_images_found = false
                    # nothing found
                    $scope.struct.img_url = ""
                    $scope.device_data.icon_name = ""
                # present non-system device group
                ns_dg = (entry for entry in $scope.struct.device_tree.group_list when $scope.struct.device_tree.ignore_cdg(entry))
                if ns_dg.length
                    $scope.device_data.device_group = ns_dg[0].name
                if $scope.struct.peer_tree.peer_list.length
                    $scope.device_data.peer = $scope.struct.peer_tree.peer_list[0].idx

                $scope.resolve_name()
                blockUI.stop()

                $scope.struct.data_ready = true
        )
    $scope.reload()

    $scope.select_image = ($event, entry) ->
        $scope.struct.img_url = entry.data_image
        $scope.device_data.icon_name = entry.name


    $scope.fix_ip_address = ($event) ->
        if $scope.device_data.ip
            $scope.struct.ip_fixed = true
        else
            $scope.struct.ip_fixed = false

    _same_search = () ->
        if $scope.device_data.full_name
            $scope.struct.same_search_pending = true
            icswSimpleAjaxCall(
                url: ICSW_URLS.MON_SEARCH_SIMILAR_NAMES
                data: {
                    fqdn: $scope.device_data.full_name
                }
                dataType: "json"
            ).then(
                (json) ->
                    $scope.struct.same_search_pending = false
                    $scope.struct.matching_names.length = 0
                    $scope.struct.matching_names_found = json.found
                    for entry in json.list
                        if entry.name == $scope.device_data.full_name
                            entry.$$tr_class = "bg-danger"
                        else if entry.ratio > 0.8
                            entry.$$tr_class = "bg-warning"
                        else
                            entry.$$tr_class = ""
                        $scope.struct.matching_names.push(entry)
            )

    $scope.device_name_changed = () ->
        if not $scope.struct.resolve_pending and $scope.device_data.full_name and not $scope.struct.ip_fixed
            $scope.resolve_name()
        if not $scope.struct.same_search_pending and $scope.device_data.full_name
            _same_search()

    $scope.resolve_name = () ->
        # clear ip
        if $scope.device_data.full_name
            $scope.device_data.ip = ""
            $scope.struct.resolve_pending = true
            icswSimpleAjaxCall(
                url: ICSW_URLS.MON_RESOLVE_NAME
                data: {
                    fqdn: $scope.device_data.full_name
                }
            ).then(
                (xml) ->
                    $scope.struct.resolve_pending = false
                    $scope.device_data.ip = $(xml).find("value[name='ip']").text()
            )

    $scope.show_device = ($event, dev_idx) ->
        $event.stopPropagation()
        $event.preventDefault()
        DeviceOverviewService($event, [$scope.struct.device_tree.all_lut[dev_idx]])

    $scope.create_device_and_edit = ($event) ->
        _create_device($event, true)

    $scope.create_device = ($event) ->
        _create_device($event, false)

    _create_device = ($event, edit_after) ->
        d_dict = $scope.device_data
        blockUI.start()
        icswSimpleAjaxCall(
            url: ICSW_URLS.DEVICE_CREATE_DEVICE
            data: {
                device_data: angular.toJson(d_dict)
            }
        ).then(
            (xml) =>
                if $(xml).find("value[name='device_pk']").length
                    _dev_pk = parseInt($(xml).find("value[name='device_pk']").text())
                    if $scope.struct.bulk_create_mode == false
                        $scope.device_data.full_name = ""
                    defer = $q.defer()
                    $scope.struct.device_tree._fetch_device(
                        _dev_pk
                        defer
                        "new device"
                    )
                    defer.promise.then(
                        (creat_msg) ->
                            new_dev = $scope.struct.device_tree.all_lut[_dev_pk]
                            # console.log _dev_pk, new_dev

                            scan_settings = {
                                manual_address: d_dict.ip
                                strict_mode: true
                                modify_peering: false
                                scan_mode: "base"
                                device: _dev_pk
                            }

                            $scope.struct.device_tree.register_device_scan($scope.struct.device_tree.all_lut[_dev_pk], scan_settings)

                            # DEVICE SELECTION
                            if $scope.device_data.dev_selection.key == "replace"
                                icswActiveSelectionService.get_selection().deselect_all_devices()
                            if $scope.device_data.dev_selection.key in ["add", "replace"]
                                icswActiveSelectionService.current().add_selection(new_dev)
                                icswActiveSelectionService.current().signal_selection_changed()

                            # why ? to get the results of the base scan ?
                            # this is very dangerous because structures created
                            # for the device will be overwritten by the fetch
                            # $timeout(
                            #    () ->
                            #        defer = $q.defer()
                            #        $scope.struct.device_tree._fetch_device(
                            #            _dev_pk
                            #            defer
                            #            "New Device"
                            #        )
                            #    5000
                            # )

                            if edit_after
                                DeviceOverviewService($event, [$scope.struct.device_tree.all_lut[_dev_pk]]).then(
                                    (show) ->
                                        blockUI.stop()
                                )
                            else if $scope.device_data.nmap_device != undefined
                                $timeout(
                                    () ->
                                        $scope.device_data.nmap_device.linked_devices.push(new_dev)
                                        init_with_device_info()
                                    0
                                )
                                blockUI.stop()
                            else
                                blockUI.stop()
                        (not_ok) ->
                            blockUI.stop()
                    )
                else
                    blockUI.stop()
            (error) ->
                blockUI.stop()
        )
])
