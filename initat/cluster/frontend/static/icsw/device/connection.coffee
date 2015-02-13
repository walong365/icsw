angular.module(
    "icsw.device.connection",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).controller("icswDeviceConnectionCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "blockUI", "icswTools", "ICSW_URLS", "icswCallAjaxService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, blockUI, icswTools, ICSW_URLS, icswCallAjaxService) ->
        $scope.devsel_list = []
        # ac settings
        $scope.ac_type = "master"
        $scope.change_ac_type = () ->
            $scope.ac_type = if $scope.ac_type == "master" then "slave" else "master"
        $scope.handle_ac = () ->
            blockUI.start()
            icswCallAjaxService
                url   : ICSW_URLS.DEVICE_MANUAL_CONNECTION
                data  : {
                    "source" : $scope.ac_host
                    "target" : $scope.ac_cd
                    "mode"   : $scope.ac_type
                }
                success : (xml) =>
                    blockUI.stop()
                    # show info
                    icswTools.parse_xml_response(xml, 30)
                    # reload (even on error)
                    $scope.reload()
        # mixins
        $scope.cd_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.cd_edit.create_template = "cd.connection.form"
        $scope.cd_edit.edit_template = "cd.connection.form"
        $scope.cd_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_CD_CONNECTION_LIST.slice(1))
        $scope.cd_edit.modify_rest_url = ICSW_URLS.REST_CD_CONNECTION_DETAIL.slice(1).slice(0, -2)
        $scope.cd_edit.new_object_at_tail = true
        $scope.cd_edit.use_promise = true

        $scope.new_devsel = (_dev_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                [ICSW_URLS.REST_DEVICE_TREE_LIST, {"pks" : angular.toJson($scope.devsel_list), "cd_connections" : true, "olp" : "backbone.device.change_connection"}],
                [ICSW_URLS.REST_CD_CONNECTION_LIST, {}]
            ])
            $q.all(wait_list).then((data) ->
                _devs = data[0]
                $scope.devices = icswTools.build_lut(_devs)
                $scope.cd_devs = []
                for entry in _devs
                    if entry.device_type_identifier == "CD" and entry.idx in $scope.devsel_list
                        entry.master_list = []
                        entry.slave_list = []
                        $scope.cd_devs.push(entry)
                $scope.cd_lut = icswTools.build_lut($scope.cd_devs)
                for _cd in data[1]
                    if _cd.parent of $scope.cd_lut
                        $scope.cd_lut[_cd.parent].slave_list.push(_cd)
                    if _cd.child of $scope.cd_lut
                        $scope.cd_lut[_cd.child].master_list.push(_cd)
            )
        $scope.modify_cd = (cd, event) ->
            $scope.cd_edit.edit(cd, event).then(
                (mod_cd) ->
                    if mod_cd != false
                        # nothing
                        true
            )
        $scope.delete_cd = (cd, dev, event) ->
            $scope.cd_edit.delete_list = undefined
            $scope.cd_edit.delete_obj(cd).then(
                (do_it) ->
                    if do_it
                        dev.master_list = (entry for entry in dev.master_list when entry.idx != cd.idx)
                        dev.slave_list  = (entry for entry in dev.slave_list  when entry.idx != cd.idx)
            )
        $scope.any_valid_devs = (dev, only_cds) ->
            return if $scope.get_valid_devs(dev, only_cds).length then true else false
        $scope.get_valid_devs = (dev, only_cds) ->
            # return all valid devices for given cd
            _ms_pks = (entry.child for entry in dev.master_list).concat((entry.parent for entry in dev.slave_list))
            valid_pks = (pk for pk in $scope.devsel_list when pk != dev.idx and pk not in _ms_pks)
            if only_cds
                valid_pks = (pk for pk in valid_pks when pk of $scope.devices and $scope.devices[pk].device_type_identifier == "CD")
            return valid_pks
        $scope.get_device_info = (pk) ->
            if pk of $scope.devices
                return $scope.devices[pk].full_name
            else
                return "#{pk} ?"
        $scope.create_master = (dev, pk) ->
            new_obj = {
                "parent" : dev.idx
                "child"  : pk
                "connection_info" : "from webfrontend"
                "created_by" : CURRENT_USER.pk
            }
            $scope.cd_edit.create_rest_url.post(new_obj).then((data) ->
                dev.slave_list.push(data)
            )
        $scope.create_slave = (dev, pk) ->
            new_obj = {
                "parent" : pk
                "child"  : dev.idx
                "connection_info" : "from webfrontend"
                "created_by" : CURRENT_USER.pk
            }
            $scope.cd_edit.create_rest_url.post(new_obj).then((data) ->
                dev.master_list.push(data)
            )
    ]
).directive("icswDeviceConnectionOverview", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.connection.overview")
        link : (scope, el, attrs) ->
            scope.$watch(attrs["devicepk"], (new_val) ->
                if new_val and new_val.length
                    scope.new_devsel(new_val)
            )
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[0])                    
                )
    }
])
