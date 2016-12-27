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
    "icsw.device.info",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools", "icsw.device.variables"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.deviceinfo")
]).service("DeviceOverviewService",
[
    "Restangular", "$rootScope", "$templateCache", "$compile", "$uibModal", "$q",
    "icswComplexModalService", "DeviceOverviewSettings",
(
    Restangular, $rootScope, $templateCache, $compile, $uibModal, $q,
    icswComplexModalService, DeviceOverviewSettings,
) ->
    return (event, device_list) ->
        # create new modal for device
        # device object with access_levels
        _defer = $q.defer()
        sub_scope = $rootScope.$new(true)
        sub_scope.devicelist = device_list
        icswComplexModalService(
            {
                message: $compile("<icsw-device-overview icsw-popup-mode='1' icsw-device-list='devicelist'></icsw-device-overview>")(sub_scope)
                title: "Device Info"
                css_class: "modal-wide modal-tall"
                closable: true
                show_callback: (modal) ->
                    DeviceOverviewSettings.open()
                    _defer.resolve("show")
            }
        ).then(
            (closeinfo) ->
                console.log "close deviceoverview #{closeinfo}"
                DeviceOverviewSettings.close()
                sub_scope.$destroy()
        )
        return _defer.promise
        # my_mixin.edit(null, devicelist[0])
        # todo: destroy sub_scope
]).service("DeviceOverviewSettings",
[
    "icswUserService", "ICSW_SIGNALS", "$rootScope",
(
    icswUserService, ICSW_SIGNALS, $rootScope,
) ->
    # default value
    _defs = {
        active_tab: "general"
        disabled_tabs: ""
    }
    is_active = false
    user = undefined
    VAR_NAME_ACT_TAB = "$$ICSW_MODE_ACTIVE_TAB"
    VAR_NAME_DISABLED_TABS = "$$ICSW_DISABLED_TABS"

    _load_user = () ->
        icswUserService.load("$$icsw_do_settings").then(
            (cur_user) ->
                user = cur_user
                if user.is_authenticated()
                    _defs.active_tab = user.get_var(VAR_NAME_ACT_TAB, _defs.mode).value
                    _defs.disabled_tabs = user.get_var(VAR_NAME_DISABLED_TABS, _defs.disabled_tabs).value
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () ->
        _load_user()
    )

    _load_user()

    set_var = (var_name, key, value) ->
        _defs[key] = value
        if user?
            user.set_string_var(var_name, value)

    return {
        is_active: () ->
            return is_active
        open: () ->
            is_active = true
        close: () ->
            is_active = false

        # mode calls
        get_mode : () ->
            return _defs.active_tab
        set_mode: (mode) ->
            return set_var(VAR_NAME_ACT_TAB, "active_tab", mode)

        # disabled tabs calls
        get_disabled_tabs: () ->
            return _defs.disabled_tabs

        set_disabled_tabs: (tabs) ->
            return set_var(VAR_NAME_DISABLED_TABS, "disabled_tabs", tabs)
    }
]).service("icswDeviceOverviewTabTemplate",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    class icswDeviceOverviewTabTemplate
        constructor: (@name, @with_meta, @right, @shownname) ->
            @template = $templateCache.get("icsw.device.info.tab.#{@name}")

]).service("icswDeviceOverviewTabs",
[
    "icswDeviceOverviewTabTemplate",
(
    icswDeviceOverviewTabTemplate,
) ->
    _list = [
        new icswDeviceOverviewTabTemplate("general", true, "", "General")
        new icswDeviceOverviewTabTemplate("network", false, "backbone.device.change_network", "Network")
        new icswDeviceOverviewTabTemplate("config", true, "backbone.device.change_config", "Configuration")
        new icswDeviceOverviewTabTemplate("category", false, "backbone.device.change_category", "Categories")
        new icswDeviceOverviewTabTemplate("location", false, "backbone.device.change_location", "Locations")
        new icswDeviceOverviewTabTemplate("variable", true, "backbone.device.change_variables", "Device Variables")
        new icswDeviceOverviewTabTemplate("devicelogs", true, "", "Device Logs")
    ]
    return _list
]).directive("icswDeviceOverview",
[
    "$compile", "DeviceOverviewSettings", "$templateCache", "icswAccessLevelService",
    "icswDeviceOverviewTabs", "ICSW_SIGNALS",
(
    $compile, DeviceOverviewSettings, $templateCache, icswAccessLevelService,
    icswDeviceOverviewTabs, ICSW_SIGNALS,
) ->
    return {
        restrict: "EA"
        replace: true
        scope: {
            devicelist: "=icswDeviceList"
            popupmode: "@icswPopupMode"
        }
        link: (scope, element, attrs) ->

            # destroy old subscope, important
            scope.$on(
                "$destroy",
                () ->
                    if sub_scope?
                        sub_scope.$destroy()
                    console.log "Destroy Device-overview scope"
            )

            scope.$on(ICSW_SIGNALS("_ICSW_DEVICE_TABS_CHANGED"), () ->
                build_template()
            )

            sub_scope = undefined

            build_scope= () ->
                sub_scope = scope.$new(true)
                icswAccessLevelService.install(sub_scope)
                # copy devicelist
                sub_scope.devicelist = (entry for entry in scope.devicelist)
                sub_scope.popupmode = scope.popupmode
                # number of total devices
                sub_scope.total_sel = scope.devicelist.length
                # number of normal (== non-meta) devices
                sub_scope.normal_sel = (dev.idx for dev in scope.devicelist when !dev.is_meta_device).length
                sub_scope.device_nmd_list = (dev for dev in scope.devicelist when !dev.is_meta_device)

                sub_scope.activate = (name) ->
                    # remember setting
                    DeviceOverviewSettings.set_mode(name)

                if sub_scope.total_sel > 1
                    sub_scope.addon_text = " (#{sub_scope.total_sel})"
                else
                    sub_scope.addon_text = ""
                if sub_scope.normal_sel > 1
                    sub_scope.addon_text_nmd = " (#{sub_scope.normal_sel})"
                else
                    sub_scope.addon_text_nmd = ""
                return sub_scope


            build_template = () ->
                if sub_scope?
                    sub_scope.$destroy()
                sub_scope = build_scope()
                # build template
                template_f = []
                _valid_names = []
                _disabled_tabs = DeviceOverviewSettings.get_disabled_tabs().split(",")
                for tab in icswDeviceOverviewTabs
                    if tab.with_meta and sub_scope.total_sel
                        _add = true
                    else if not tab.with_meta and sub_scope.normal_sel
                        _add = true
                    else
                        _add = false
                    if tab.name in _disabled_tabs
                        _add = false
                    else if tab.right
                        if not sub_scope.acl_read(null, tab.right)
                            _add = false
                    if _add
                        _valid_names.push(tab.name)
                        template_f.push("<uib-tab select='activate(\"#{tab.name}\")'>#{tab.template}</uib-tab>")

                _valid_names.push("$$modify")
                template_f.push($templateCache.get("icsw.device.info.tab.tab_setup"))

                sub_scope.active_tab = _.indexOf(_valid_names, DeviceOverviewSettings.get_mode())
                if sub_scope.active_tab < 0
                    sub_scope.active_tab = 0

                template = template_f.join("")
                template = "<uib-tabset active='active_tab'>#{template}</uib-tabset>"
                # console.log "template=", template
                new_el = $compile(template)(sub_scope)
                element.children().remove()
                element.append(new_el)

            build_template()
    }
]).directive("icswDeviceInfoTabModify",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        controller: "icswDeviceInfoTabModifyCtrl"
        template: $templateCache.get("icsw.device.info.tab.modify")
        scope: true
    }
]).controller("icswSimpleDeviceInfoOverviewCtrl",
[
    "$scope", "Restangular", "$q", "ICSW_URLS", "$timeout", "icswTools",
    "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", "icswDeviceTreeService", "icswMonitoringBasicTreeService",
    "icswAccessLevelService", "icswActiveSelectionService", "icswDeviceBackup", "icswDeviceGroupBackup",
    "icswDeviceTreeHelperService",
(
    $scope, Restangular, $q, ICSW_URLS, $timeout, icswTools,
    $rootScope, ICSW_SIGNALS, icswDomainTreeService, icswDeviceTreeService, icswMonitoringBasicTreeService,
    icswAccessLevelService, icswActiveSelectionService, icswDeviceBackup, icswDeviceGroupBackup,
    icswDeviceTreeHelperService,
) ->
    icswAccessLevelService.install($scope)

    $scope.struct = {
        # data is valid
        data_valid: false
        # waiting clients
        waiting_clients: 0
        # device tree
        device_tree: undefined
        # structured list, includes template name
        slist: []
        # list unable to display (too many devs)
        tmd_list: []
        # active tab
        active_tab: 0
    }
    # create info fields
    create_small_info_fields = (struct) ->
        obj = struct.edit_obj
        if struct.is_devicegroup
            obj.$$full_device_name = obj.name.substr(8)
            # not really needed
            obj.$$snmp_scheme_info = "N/A"
            obj.$$snmp_info = "N/A"
            obj.$$ip_info = "N/A"
        else
            obj.$$full_device_name = obj.full_name

    $scope.new_devsel = (in_list) ->
        $scope.struct.data_valid = false
        if in_list.length > 0
            $scope.struct.slist.length = 0
            $scope.struct.tmd_list.length = 0
            icswDeviceTreeService.load($scope.$id).then(
                (tree) ->
                    $scope.struct.device_tree = tree
                    trace_devices =  $scope.struct.device_tree.get_device_trace(in_list)
                    dt_hs = icswDeviceTreeHelperService.create($scope.struct.device_tree, trace_devices)
                    $q.all(
                        [
                            icswDomainTreeService.load($scope.$id)
                            $scope.struct.device_tree.enrich_devices(
                                dt_hs
                                [
                                    "network_info", "monitoring_hint_info", "disk_info", "com_info",
                                    "snmp_info", "snmp_schemes_info", "scan_lock_info",
                                ]
                            )
                       ]
                    ).then(
                        (data) ->
                            $scope.struct.domain_tree = data[0]
                            MAX_DEVS_TO_SHOW = 10
                            for dev in in_list
                                if dev.is_meta_device
                                    new_struct = {
                                        edit_obj: dev
                                        is_devicegroup: true
                                        init_called: false
                                    }
                                else
                                    new_struct = {
                                        edit_obj: dev
                                        is_devicegroup: false
                                        init_called: false
                                    }
                                create_small_info_fields(new_struct)
                                if $scope.struct.slist.length >= MAX_DEVS_TO_SHOW
                                    $scope.struct.tmd_list.push(new_struct)
                                else
                                    $scope.struct.slist.push(new_struct)
                            $scope.struct.data_valid = true
                            $timeout(
                                () ->
                                    # delay activation (otherwise the subcontrollers
                                    # will simply not be here)
                                    $scope.activate_tab(null, $scope.struct.slist[0])
                                0
                            )
                    )
            )
        else
            $scope.struct.slist.length = 0
            $scope.struct.data_valid = true
            $scope.struct.active_tab = null

    $scope.activate_tab = (event, entry) ->
        $scope.struct.active_tab = entry.edit_obj.idx
        $scope.$broadcast(ICSW_SIGNALS("_ICSW_DEVICE_INFO_ACTIVATE_TAB"), entry.edit_obj.idx)

    $scope.show_device = (event, entry) ->
        _.remove(
            $scope.struct.tmd_list,
            (el) ->
                return el.edit_obj.idx == entry.edit_obj.idx
        )
        last = _.last($scope.struct.slist)
        $scope.struct.slist.push(entry)
        _.remove($scope.struct.slist, (el) -> return el.edit_obj.idx == last.edit_obj.idx)
        $scope.struct.tmd_list.push(last)
        icswTools.order_in_place(
            $scope.struct.tmd_list
            ["edit_obj.$$full_device_name"]
            ["asc"]
        )
        icswTools.order_in_place(
            $scope.struct.slist
            ["edit_obj.$$full_device_name"]
            ["asc"]
        )


]).controller("icswDeviceInfoTabModifyCtrl",
[
    "$scope", "icswDeviceOverviewTabs", "DeviceOverviewSettings", "ICSW_SIGNALS",
(
    $scope, icswDeviceOverviewTabs, DeviceOverviewSettings, ICSW_SIGNALS,
) ->
    $scope.struct = {
        # tab list
        tab_list: []
        # currently disabled
        disabled_str: ""
    }
    update = () ->
        $scope.struct.disabled_str = DeviceOverviewSettings.get_disabled_tabs()
        disabled_tabs = $scope.struct.disabled_str.split(",")
        $scope.struct.tab_list = []
        for entry in icswDeviceOverviewTabs
            $scope.struct.tab_list.push(
                {
                    name: entry.name
                    $$active: entry.name not in disabled_tabs
                    shownname: entry.shownname
                }
            )

    update()

    $scope.modify_tabs = ($event) ->
        _new_disabled_str = (entry.name for entry in $scope.struct.tab_list when not entry.$$active).join(",")
        if _new_disabled_str != $scope.struct.disabled_str
            $scope.struct.disabled_str = _new_disabled_str
            DeviceOverviewSettings.set_disabled_tabs($scope.struct.disabled_str)
            $scope.$emit(ICSW_SIGNALS("_ICSW_DEVICE_TABS_CHANGED"))

]).directive("icswSimpleDeviceInfo",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        controller: "icswSimpleDeviceInfoOverviewCtrl"
        template: $templateCache.get("icsw.device.info.overview")
        scope: true
    }
]).directive("icswDeviceInfoDevice",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "EA"
        controller: "icswSimpleDeviceInfoCtrl"
        scope: {
            icsw_struct: "=icswStruct"
        }
        link: (scope, element, attrs) ->
            scope.install_template = () ->
                if scope.icsw_struct.is_devicegroup
                    _t_name = "icsw.devicegroup.info.form"
                else
                    _t_name = "icsw.device.info.form"
                element.append($compile($templateCache.get(_t_name))(scope))
    }
]).controller("icswSimpleDeviceInfoCtrl",
[
    "$scope", "Restangular", "$q", "ICSW_URLS",
    "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", "icswDeviceTreeService", "icswMonitoringBasicTreeService",
    "icswAccessLevelService", "icswActiveSelectionService", "icswDeviceBackup", "icswDeviceGroupBackup",
    "icswDeviceTreeHelperService", "icswComplexModalService", "toaster", "$compile", "$templateCache",
    "icswCategoryTreeService",
(
    $scope, Restangular, $q, ICSW_URLS,
    $rootScope, ICSW_SIGNALS, icswDomainTreeService, icswDeviceTreeService, icswMonitoringBasicTreeService,
    icswAccessLevelService, icswActiveSelectionService, icswDeviceBackup, icswDeviceGroupBackup,
    icswDeviceTreeHelperService, icswComplexModalService, toaster, $compile, $templateCache,
    icswCategoryTreeService,
) ->
    $scope.struct = {
        # data is valid
        data_valid: false
        # device tree
        device_tree: undefined
        # monitoring tree
        monitoring_tree: undefined
        # domain tree
        domain_tree: undefined
        # category tree
        category_tree: undefined
        # device group
        is_devicegroup: false
    }
    create_info_fields = (obj) ->
        if $scope.struct.is_devicegroup
            # not really needed
            obj.$$snmp_scheme_info = "N/A"
            obj.$$snmp_info = "N/A"
            obj.$$ip_info = "N/A"
            hints = "---"
            cats = "---"
        else
            _sc = obj.snmp_schemes
            if _sc.length
                obj.$$snmp_scheme_info = ("#{_entry.snmp_scheme_vendor.name}.#{_entry.name}" for _entry in _sc).join(", ")
            else
                obj.$$snmp_scheme_info = "none"
            ip_list = []
            for _nd in obj.netdevice_set
                for _ip in _nd.net_ip_set
                    ip_list.push(_ip.ip)
            obj.$$ip_info = if ip_list.length then ip_list.join(", ") else "none"
            _sc = obj.DeviceSNMPInfo
            if _sc
                obj.$$snmp_info = _sc.description
            else
                obj.$$snmp_info = "none"
            if obj.monitoring_hint_set.length
                mhs = obj.monitoring_hint_set
                hints = "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
            else
                hints = "---"

            # categories
            _cats = $scope.struct.category_tree.get_device_categories(obj)
            _asset_cats = (entry for entry in _cats when entry.asset)
            if _cats.length
                _cats_info = (entry.name for entry in _cats).join(", ")
            else
                _cats_info = "---"
            obj.$$category_info = _cats_info 
            if _asset_cats.length
                _asset_cats_info = (entry.name for entry in _asset_cats).join(", ")
            else
                _asset_cats_info = "---"
            obj.$$asset_category_info = _asset_cats_info 

        # monitoring image
        img_url = ""
        if obj.mon_ext_host
            for entry in $scope.struct.monitoring_tree.mon_ext_host_list
                if entry.idx == obj.mon_ext_host
                    img_url = entry.data_image
        obj.$$image_source = img_url
        obj.$$monitoring_hint_info = hints

    icswAccessLevelService.install($scope)

    _dereg_0 = $rootScope.$on(ICSW_SIGNALS("ICSW_CATEGORY_TREE_CHANGED"), () ->
        if $scope.struct.data_valid
            create_info_fields($scope.edit_obj)
    )

    _dereg_1 = $scope.$on(ICSW_SIGNALS("_ICSW_DEVICE_INFO_ACTIVATE_TAB"), (event, idx) ->
        if $scope.icsw_struct.edit_obj.idx == idx
            if not $scope.icsw_struct.init_called
                $scope.icsw_struct.init_called = true
                $scope.do_init()
        # console.log "*", event, idx, $scope.icsw_struct
    )

    $scope.$on("$destroy", () ->
        _dereg_0()
        _dereg_1()
    )

    $scope.do_init = () ->
        # defer = $q.defer()
        $scope.struct.data_valid = false
        $scope.struct.is_devicegroup = $scope.icsw_struct.is_devicegroup
        $q.all(
            [
                icswDeviceTreeService.load($scope.$id)
                icswMonitoringBasicTreeService.load($scope.$id)
                icswDomainTreeService.load($scope.$id)
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.device_tree = data[0]
                $scope.struct.monitoring_tree = data[1]
                # console.log data[1]
                $scope.struct.domain_tree = data[2]
                $scope.struct.category_tree = data[3]
                if $scope.icsw_struct.is_devicegroup
                    $scope.edit_obj = $scope.struct.device_tree.get_group($scope.icsw_struct.edit_obj)
                else
                    $scope.edit_obj = $scope.icsw_struct.edit_obj
                $scope.edit_obj.$$show_atfv = false
                create_info_fields($scope.edit_obj)
                # console.log $scope.edit_obj
                $scope.struct.data_valid = true
                $scope.install_template()
                # defer.resolve("done")
        )

        # return defer.promise

    $scope.modify = () ->
        if $scope.struct.is_devicegroup
            dbu = new icswDeviceGroupBackup()
            template_name = "icsw.devicegroup.info.edit.form"
            title = "Modify Device Group Settings"
        else
            dbu = new icswDeviceBackup()
            template_name = "icsw.device.info.edit.form"
            title = "Modify Device Settings"
        dbu.create_backup($scope.edit_obj)
        sub_scope = $scope.$new(true)
        sub_scope.edit_obj = $scope.edit_obj
        sub_scope.struct = $scope.struct

        # for fields, tree can be the basic or the cluster tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                title: title
                # removed modal-form due to horrible display
                css_class: "modal-wide"
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        sub_scope.edit_obj.put().then(
                            (ok) ->
                                $scope.struct.device_tree.reorder()
                                d.resolve("updated")
                            (not_ok) ->
                                d.reject("not updated")
                        )
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup($scope.edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                # recreate info fields
                create_info_fields($scope.edit_obj)
        )

    $scope.modify_categories = (for_asset) ->
        dbu = new icswDeviceBackup()
        template_name = "icsw.device.category.edit"
        title = "Modify DeviceCategories"
        dbu.create_backup($scope.edit_obj)
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = $scope.edit_obj
        sub_scope.asset_filter = for_asset

        # for fields, tree can be the basic or the cluster tree

        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                title: title
                ok_label: "Modify"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("updated")
                    return d.promise
                cancel_callback: (modal) ->
                    dbu.restore_backup($scope.edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                # recreate info fields
                create_info_fields($scope.edit_obj)
        )

])
