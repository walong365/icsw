# Copyright (C) 2016 init.at
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

# variable related module

static_inventory_overview = angular.module(
    "icsw.device.asset.static",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.assetstaticoverview")
]).directive("icswDeviceAssetStaticOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.asset.static.overview")
        controller: "icswDeviceAssetStaticOverviewCtrl"
        scope: true
    }
]).controller("icswDeviceAssetStaticOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "blockUI",
    "icswTools", "icswSimpleAjaxCall", "ICSW_URLS", "icswAssetHelperFunctions",
    "icswDeviceTreeService", "icswDeviceTreeHelperService", "$timeout",
    "icswDispatcherSettingTreeService", "Restangular", "icswCategoryTreeService",
    "icswStaticAssetTemplateTreeService", "DeviceOverviewService",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, blockUI,
    icswTools, icswSimpleAjaxCall, ICSW_URLS, icswAssetHelperFunctions,
    icswDeviceTreeService, icswDeviceTreeHelperService, $timeout,
    icswDispatcherSettingTreeService, Restangular, icswCategoryTreeService,
    icswStaticAssetTemplateTreeService, DeviceOverviewService,
) ->
    $scope.struct = {
        device_tree: undefined
        category_tree: undefined
        staticasset_tree: undefined
        hidden_static_asset_template_types: undefined
        data_loaded: false

        # easier to handle data structures
        categories: []

        static_asset_tabs: {}
    }

    $q.all(
        [
            icswDeviceTreeService.load($scope.$id)
            icswCategoryTreeService.load($scope.$id)
            icswStaticAssetTemplateTreeService.load($scope.$id)
            icswSimpleAjaxCall({
                url: ICSW_URLS.ASSET_HIDDEN_STATIC_ASSET_TEMPLATE_TYPE_MANAGER
                data:
                    action: "read"
                dataType: 'json'
            })
        ]).then(
                (data) ->
                    $scope.struct.device_tree = data[0]
                    $scope.struct.category_tree = data[1]
                    $scope.struct.staticasset_tree = data[2]
                    $scope.struct.hidden_static_asset_template_types = (obj.type for obj in data[3])

                    console.log($scope.hidden_static_asset_template_types)

                    $scope.struct.categories.length = 0

                    for category in $scope.struct.category_tree.asset_list
                        o = {
                            name: category.name
                            devices: []
                        }

                        for device_id in category.reference_dict.device
                            o.devices.push(data[0].all_lut[device_id])

                        $scope.struct.categories.push(o)

                    idx_list = []

                    for obj in $scope.struct.staticasset_tree.list
                        idx_list.push(obj.idx)

                    icswSimpleAjaxCall({
                        url: ICSW_URLS.ASSET_GET_FIELDVALUES_FOR_TEMPLATE
                        data:
                            idx_list: idx_list
                        dataType: 'json'
                    }).then(
                        (result) ->
                            static_assets = []

                            for obj in $scope.struct.staticasset_tree.list
                                static_assets.push(obj)
                                obj.$$show_devices_inventory_static_overview = false

                                if $scope.struct.static_asset_tabs[obj.type] == undefined
                                    $scope.struct.static_asset_tabs[obj.type] = []

                                $scope.struct.static_asset_tabs[obj.type].push(obj)


                            for static_asset in static_assets
                                static_asset.$$fields = result.data[static_asset.idx]
                                static_asset.$$devices = {}
                                static_asset.$$inventory_static_status = 0

                                for ordering_num in Object.getOwnPropertyNames(static_asset.$$fields)
                                    for field_value in static_asset.$$fields[ordering_num]["list"]
                                        if static_asset.$$fields[ordering_num].status > static_asset.$$inventory_static_status
                                            static_asset.$$inventory_static_status = static_asset.$$fields[ordering_num].status

                                        device = $scope.struct.device_tree.all_lut[field_value.device_idx]
                                        if device.$$static_field_values == undefined
                                            device.$$static_field_values = {}

                                        if device.$$static_field_values[static_asset.idx] == undefined
                                            device.$$static_field_values[static_asset.idx] = {}

                                        device.$$static_field_values[static_asset.idx][ordering_num] = field_value
                                        if !(field_value.device_idx in static_asset.$$devices)
                                            static_asset.$$devices[field_value.device_idx] = device

                                            field_value.$$device = $scope.struct.device_tree.all_lut[field_value.device_idx]

                                for ordering_num in Object.getOwnPropertyNames(static_asset.$$fields)
                                    for device_num in Object.getOwnPropertyNames(static_asset.$$devices)
                                        if static_asset.$$devices[device_num].$$static_field_values[static_asset.idx][ordering_num] == undefined
                                            o = {
                                                value: static_asset.$$fields[ordering_num].aggregate
                                            }

                                            static_asset.$$devices[device_num].$$static_field_values[ordering_num] = o

                                static_asset.$$expand_devices_button_disabled = true
                                for device_num in Object.getOwnPropertyNames(static_asset.$$devices)
                                    static_asset.$$expand_devices_button_disabled = false
                                    device = static_asset.$$devices[device_num]
                                    if device.$$inventory_static_status == undefined
                                        device.$$inventory_static_status = {}
                                    device.$$inventory_static_status[static_asset.idx] = 0

                                    for ordering_num in Object.getOwnPropertyNames(device.$$static_field_values[static_asset.idx])
                                        if device.$$static_field_values[static_asset.idx][ordering_num].status > device.$$inventory_static_status[static_asset.idx]
                                            device.$$inventory_static_status[static_asset.idx] = device.$$static_field_values[static_asset.idx][ordering_num].status


                            $scope.struct.data_loaded = true

                        (not_ok) ->
                            console.log(not_ok)
                    )
        )

    $scope.show_devices = ($event, obj) ->
        obj.$$show_devices_inventory_static_overview = !obj.$$show_devices_inventory_static_overview

    $scope.show_device = ($event, device) ->
        DeviceOverviewService($event, [device])

    $scope.hide_static_asset_type = (static_asset_type_name) ->
        icswSimpleAjaxCall({
            url: ICSW_URLS.ASSET_HIDDEN_STATIC_ASSET_TEMPLATE_TYPE_MANAGER
            data:
                action: "write"
                type: static_asset_type_name
            dataType: 'json'
        }).then(
            $scope.struct.hidden_static_asset_template_types.push(static_asset_type_name)
        )

    $scope.unhide_static_asset_type = (static_asset_type_name) ->
        icswSimpleAjaxCall({
            url: ICSW_URLS.ASSET_HIDDEN_STATIC_ASSET_TEMPLATE_TYPE_MANAGER
            data:
                action: "delete"
                type: static_asset_type_name
            dataType: 'json'
        }).then(

            _.pull($scope.struct.hidden_static_asset_template_types, static_asset_type_name)
        )
]).directive("icswStaticAssetTemplateOverview",
[
    "ICSW_URLS", "Restangular",
(
    ICSW_URLS, Restangular
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.static.asset.template.overview"
        controller: "icswStaticAssetTemplateOverviewCtrl"
    }
]).service("icswStaticAssetFunctions",
[
    "$q",
(
    $q,
) ->
    info_dict = {
        asset_type: [
            [1, "License", ""]
            [2, "Contract", ""]
            [3, "Hardware", ""]
        ]
        field_type: [
            [1, "Integer", ""]
            [2, "String", ""]
            [3, "Date", ""]
            [4, "Text", ""]
        ]
    }
    # list of dicts for forms
    form_dict = {}
    # create forward and backward resolves
    res_dict = {}
    for name, _list of info_dict
        res_dict[name] = {}
        form_dict[name] = []
        for [_idx, _str, _class] in _list
            # forward resolve
            res_dict[name][_idx] = [_str, _class]
            # backward resolve
            res_dict[name][_str] = [_idx, _class]
            res_dict[name][_.lowerCase(_str)] = [_idx, _class]
            # form dict
            form_dict[name].push({idx: _idx, name: _str})

    _resolve = (name, key, idx) ->
        if name of res_dict
            if key of res_dict[name]
                return res_dict[name][key][idx]
            else
                console.error "unknown key #{key} for name #{name} in resolve"
                return "???"
        else
            console.error "unknown name #{name} in resolve"
            return "????"

    _set_default_value = (field) ->
        field.default_value_date = moment(field.$$default_date).format("DD.MM.YYYY")

    _get_default_value = (field) ->
        # set $$default_value according to type
        if field.field_type == 1
            _def_val = field.default_value_int
        else if field.field_type == 2
            _def_val = field.default_value_str
        else if field.field_type == 3
            _def_val = field.default_value_date
            field.$$default_date = moment(field.default_value_date).toDate()
        else if field.field_type == 4
            # text
            _def_val = field.default_value_text
        else
            _def_val = none
        field.$$default_value = _def_val
        return _def_val

    return {
        resolve: (name, key) ->
            return _resolve(name, key, 0)

        get_default_value: (field) ->
            # convert to editable format
            return _get_default_value(field)

        set_default_value: (field) ->
            # convert back to storable format
            return _set_default_value(field)

        get_class: (name, key) ->
            return _resolve(name, key, 1)

        get_form_dict: (name) ->
            return form_dict[name]
    }

]).controller("icswStaticAssetTemplateOverviewCtrl",
[
    "$scope", "icswDeviceTreeService", "$q", "icswMonitoringBasicTreeService", "icswComplexModalService",
    "$templateCache", "$compile", "icswStaticAssetTemplateBackup", "toaster", "blockUI", "Restangular",
    "ICSW_URLS", "icswStaticAssetTemplateTreeService", "icswDispatcherSettingTreeService", "icswComCapabilityTreeService",
    "icswToolsSimpleModalService", "icswUserService", "icswUserGroupRoleTreeService", "icswStaticAssetFunctions",
    "icswStaticAssetTemplateFieldBackup", "$timeout",
(
    $scope, icswDeviceTreeService, $q, icswMonitoringBasicTreeService, icswComplexModalService,
    $templateCache, $compile, icswStaticAssetTemplateBackup, toaster, blockUI, Restangular,
    ICSW_URLS, icswStaticAssetTemplateTreeService, icswDispatcherSettingTreeService, icswComCapabilityTreeService,
    icswToolsSimpleModalService, icswUserService, icswUserGroupRoleTreeService, icswStaticAssetFunctions,
    icswStaticAssetTemplateFieldBackup, $timeout,
) ->
    $scope.struct = {
        # loading
        loading: false
        # dispatch tree
        template_tree: undefined
        # user
        user: undefined
        # user and group tree
        user_group_tree: undefined
    }
    _load = () ->
        $scope.struct.loading = true
        $q.all(
            [
                icswStaticAssetTemplateTreeService.load($scope.$id)
                icswUserService.load($scope.id)
                icswUserGroupRoleTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.template_tree = data[0]
                # salt reference contents
                $scope.struct.template_tree.add_references()
                $scope.struct.user = data[1].user
                $scope.struct.user_group_tree = data[2]
                # get monitoring masters and slaves
                $scope.struct.loading = false

        )
    _load()

    $scope.delete = ($event, obj) ->
        icswToolsSimpleModalService("Really delete Schedule '#{obj.name}' ?").then(
            () =>
                blockUI.start("deleting...")
                $scope.struct.dispatch_tree.delete_dispatcher_setting(obj).then(
                    (ok) ->
                        console.log "schedule deleted"
                        blockUI.stop()
                    (notok) ->
                        blockUI.stop()
                )
        )


    modify_or_create_field = ($event, parent_scope, as_temp, field, create) ->
        s2_scope = parent_scope.$new(true)
        if create
            field = {
                static_asset_template: as_temp.idx
                name: "New field"
                default_value_str: ""
                default_value_int: 0
                default_value_date: moment().toDate()
                field_type: 2
                ordering: as_temp.staticassettemplatefield_set.length
                # warn and critical for date
                date_check: false
                date_warn_value: 60
                date_critical_value: 30
            }
            _ok_label = "create"
        else
            f_bu = new icswStaticAssetTemplateFieldBackup()
            f_bu.create_backup(field)
            _ok_label = "modify"
        s2_scope.edit_obj = field
        s2_scope.create = create

        s2_scope.open_picker = ($event) ->
            s2_scope.datepicker_options.open = true

        s2_scope.button_bar = {
            show: true
            now: {
                show: true
                text: 'Now'
            },
            today: {
                show: true
                text: 'Today'
            },
            close: {
                show: true
                text: 'Close'
            }
        }
        s2_scope.datepicker_options = {
            date_options: {
                format: "dd.MM.yyyy"
                formatYear: "yyyy"
                minDate: new Date(2000, 1, 1)
                startingDay: 1
                minMode: "day"
                datepickerMode: "day"
            }
            time_options: {
                showMeridian: false
            }
            open: false
        }
        s2_scope.field_type_list = icswStaticAssetFunctions.get_form_dict("field_type")
        s2_scope.template = as_temp

        # functions
        s2_scope.field_changed = () ->
            $timeout(
                () ->
                    $scope.struct.template_tree.salt_field(s2_scope.edit_obj)
                0
            )

        s2_scope.field_changed()

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.static.asset.field.form"))(s2_scope)
                title: "Static Inventory Template Field '#{s2_scope.edit_obj.name}'"
                ok_label: _ok_label
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if s2_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        blockUI.start("saving Field...")
                        icswStaticAssetFunctions.set_default_value(s2_scope.edit_obj)
                        if create
                            $scope.struct.template_tree.create_field(parent_scope.edit_obj, s2_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("done")
                                (notok) ->
                                    blockUI.stop()
                                    d.reject("not done")
                            )
                        else
                            $scope.struct.template_tree.update_field(parent_scope.edit_obj, s2_scope.edit_obj).then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("done")
                                (notok) ->
                                    blockUI.stop()
                                    d.reject("not done")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        f_bu.restore_backup(field)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                $scope.struct.template_tree.link()
                s2_scope.$destroy()
        )

    $scope.create_or_edit = ($event, obj, create) ->
        if create
            obj = {
                name: "new Template"
                description: "New StaticAssetTemplate"
                user: $scope.struct.user.idx
                system_template: false
                parent_template: null
                staticassettemplatefield_set: []
                type: "standard"
                multi: false
                enabled: true
            }

            _ok_label = "Create"
        else
            dbu = new icswStaticAssetTemplateBackup()
            dbu.create_backup(obj)
            _ok_label = "Modify"

        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = obj

        sub_scope.create = create

        sub_scope.get_template_types = (search) ->
            new_types = $scope.struct.template_tree.static_asset_type_keys.slice()
            if (search && new_types.indexOf(search) == -1)
                new_types.unshift(search)

            return new_types

        sub_scope.modify_or_create_field = ($event, as_temp, field, create) ->
            modify_or_create_field($event, sub_scope, as_temp, field, create)

        sub_scope.delete_field = ($event, as_temp, field) ->
            icswToolsSimpleModalService("Really delete field #{field.name} ?").then(
                (del) ->
                    blockUI.start()
                    $scope.struct.template_tree.delete_field(as_temp, field).then(
                        (ok) ->
                            blockUI.stop()
                        (notok) ->
                            blockUI.stop()
                    )
            )

        sub_scope.move_field = ($event, field, up) ->
            blockUI.start("reorder...")
            $scope.struct.template_tree.move_field(sub_scope.edit_obj, field, up).then(
                (done) ->
                    blockUI.stop()
            )

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.static.asset.template.form"))(sub_scope)
                title: "Static Inventory Template #{sub_scope.edit_obj.name}"
                ok_label: _ok_label
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        if create
                            blockUI.start("creating new Template ...")
                            console.log(sub_scope.edit_obj)
                            $scope.struct.template_tree.create_template(sub_scope.edit_obj).then(
                                (new_obj) ->
                                    blockUI.stop()
                                    d.resolve("created")
                                (notok) ->
                                    blockUI.stop()
                                    d.reject("not created")
                            )
                        else
                            blockUI.start("saving Template ...")
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_STATIC_ASSET_TEMPLATE_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (ok) ->
                                    blockUI.stop()
                                    d.resolve("saved")
                                (not_ok) ->
                                    blockUI.stop()
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create
                        dbu.restore_backup(obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                $scope.struct.template_tree.link()
                $scope.struct.template_tree.add_references()
                sub_scope.$destroy()
        )

    $scope.copy = ($event, obj) ->
        sub_scope = $scope.$new(false)
        sub_scope.src_obj = obj
        sub_scope.new_obj = {
            name: "Copy of #{obj.name}"
            description: obj.description
        }

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.static.asset.template.copy.form"))(sub_scope)
                title: "Copy Template #{sub_scope.src_obj.name}"
                ok_label: "Copy"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        blockUI.start("Copying Template ...")
                        $scope.struct.template_tree.copy_template(
                            sub_scope.src_obj
                            sub_scope.new_obj
                            $scope.struct.user
                        ).then(
                            (new_obj) ->
                                blockUI.stop()
                                d.resolve("created")
                            (notok) ->
                                blockUI.stop()
                                d.reject("not created")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                $scope.struct.template_tree.link()
                sub_scope.$destroy()
        )

    $scope.delete = ($event, obj) ->
        icswToolsSimpleModalService("Really delete StaticAssetTemplate '#{obj.name}' ?").then(
            () =>
                blockUI.start("deleting...")
                $scope.struct.template_tree.delete_template(obj).then(
                    (ok) ->
                        console.log "StaticAsset deleted"
                        blockUI.stop()
                    (notok) ->
                        blockUI.stop()
                )
        )


])
