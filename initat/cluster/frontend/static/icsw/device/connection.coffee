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
    "icsw.device.connection",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.deviceconnection"
            {
                url: "/deviceconnection"
                templateUrl: "icsw/main/device/connection.html"
                icswData:
                    pageTitle: "Device Connections"
                    rights: ["device.change_connection"]
                    menuEntry:
                        menukey: "dev"
                        name: "Device connections"
                        icon: "fa-plug"
                        ordering: 25
            }
    )
]).controller("icswDeviceConnectionCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "blockUI", "ICSW_URLS", "icswSimpleAjaxCall", "icswCDConnectionBackup",
    "icswUserService", "icswDeviceTreeService", "icswDeviceTreeHelperService",
    "icswToolsSimpleModalService", "icswComplexModalService",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, blockUI, ICSW_URLS, icswSimpleAjaxCall, icswCDConnectionBackup,
    icswUserService, icswDeviceTreeService, icswDeviceTreeHelperService,
    icswToolsSimpleModalService, icswComplexModalService,
) ->
    $scope.devsel_list = []
    # ac settings
    $scope.ac_type = "master"
    $scope.change_ac_type = () ->
        $scope.ac_type = if $scope.ac_type == "master" then "slave" else "master"

    $scope.handle_ac = () ->
        return
        blockUI.start()
        icswSimpleAjaxCall(
            url   : ICSW_URLS.DEVICE_MANUAL_CONNECTION
            data  : {
                "source": $scope.ac_host
                "target": $scope.ac_cd
                "mode": $scope.ac_type
            }
        ).then(
            (xml) ->
                blockUI.stop()
                # show info
                # icswParseXMLResponseService(xml, 30)
                # reload (even on error)
        )
    $scope.struct = {
        # device tree
        device_tree: undefined
        # current user
        user: undefined
        # all devices
        devices: []
        # controlling devices
        cd_devices: []
        # helper service
        helper_service: undefined
    }

    $scope.new_devsel = (dev_sel) ->
        devs = (dev for dev in dev_sel when not dev.is_meta_device)
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswUserService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.user = data[1]
                hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, devs)
                $scope.struct.device_tree.enrich_devices(hs, ["device_connection_info", "snmp_schemes_info", "com_info"]).then(
                    (done) ->
                        $scope.struct.helper_service = hs
                        $scope.struct.devices.length = 0
                        $scope.struct.cd_devices.length = 0
                        for dev in devs
                            # get controlling devices
                            _is_cd = false
                            $scope.struct.devices.push(dev)
                            for _com in dev.com_capability_list
                                if _com.matchcode == "ipmi"
                                    _is_cd = true
                            for _scheme in dev.snmp_schemes
                                if _scheme.power_control
                                    _is_cd = true
                            dev.$$is_cd = _is_cd
                            if dev.$$is_cd
                                $scope.struct.cd_devices.push(dev)
                        $scope.build_helper_lists()
                        console.log "done"
                )
        )

    # helper functions
    $scope.build_helper_lists = () ->
        _dt = $scope.struct.device_tree
        for dev in $scope.struct.cd_devices
            _fix_list = (in_list) ->
                for _entry in in_list
                    _entry.$$parent = _dt.all_lut[_entry.parent].full_name
                    _entry.$$child = _dt.all_lut[_entry.child].full_name
            _fix_list(dev.$$master_list)
            _fix_list(dev.$$slave_list)
            _ref_pks = (entry.parent for entry in dev.$$master_list).concat(
                (entry.child for entry in dev.$$slave_list)
            )
            _valid_devs = (_dev for _dev in $scope.struct.devices when dev.idx != _dev.idx and _dev.idx not in _ref_pks)
            dev.$$cd_valid_list = _valid_devs
            dev.$$cd_valid_list_cd = (_dev for _dev in _valid_devs when _dev.$$is_cd)

    $scope.delete_connection = ($event, cd) ->
        icswToolsSimpleModalService("Really delete connection ?").then(
            (ok) ->
                $scope.struct.device_tree.delete_device_connection(cd, $scope.struct.helper_service).then(
                    (del_ok) ->
                        console.log "deleted cd"
                        $scope.build_helper_lists()
                )
        )

    $scope.modify_connection = ($event, cd) ->
        sub_scope = $scope.$new(false)
        dbu = new icswCDConnectionBackup()
        dbu.create_backup(cd)
        sub_scope.edit_obj = cd
        _dt = $scope.struct.device_tree
        sub_scope.cd_info = "from #{_dt.all_lut[cd.parent].full_name} to #{_dt.all_lut[cd.child].full_name}"
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.cd.connection.form"))(sub_scope)
                ok_label: "Modify"
                title: "Edit DeviceConnection"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_CD_CONNECTION_DETAIL.slice(1).slice(0, -2))
                        sub_scope.edit_obj.put().then(
                            (data) ->
                                d.resolve("save")
                            (reject) ->
                                d.reject("not saved")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup(cd)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "CD requester closed, trigger redraw"
                sub_scope.$destroy()
                # trigger rebuild of lists
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
                # recreate helper luts
        )


    $scope.create_connection = (dev, child, mode) ->
        _new_obj = {
            connection_info: "from webfrontend"
            created_by: $scope.struct.user.idx
        }
        if mode == "master"
            _new_obj.parent = dev.idx
            _new_obj.child = child.idx
        else
            _new_obj.parent = child.idx
            _new_obj.child = dev.idx
        $scope.struct.device_tree.create_device_connection(_new_obj, $scope.struct.helper_service).then(
            (new_cd) ->
                $scope.build_helper_lists()
        )

]).directive("icswDeviceConnectionOverview",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.connection.overview")
        controller: "icswDeviceConnectionCtrl"
    }
])
