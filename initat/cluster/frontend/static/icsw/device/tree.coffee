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
device_module = angular.module(
    "icsw.device.tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "smart-table",
        "icsw.tools.table", "icsw.tools", "icsw.tools.button", "icsw.tools.dialog",
    ]
).controller("icswDeviceTreeCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "Restangular",  "restDataSource", "$q", "$timeout",
     "$modal", "array_lookupFilter", "show_dtnFilter", "msgbus", "blockUI", "icswTools", "ICSW_URLS", "icswToolsButtonConfigService",
     "icswCallAjaxService", "icswParseXMLResponseService", "icswToolsSimpleModalService", "toaster", "icswDialogDeleteObjects",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $timeout,
    $modal, array_lookupFilter, show_dtnFilter, msgbus, blockUI, icswTools, ICSW_URLS, icswToolsButtonConfigService,
    icswCallAjaxService, icswParseXMLResponseService, icswToolsSimpleModalService, toaster, icswDialogDeleteObjects) ->
        $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
        $scope.initial_load = true
        $scope.rest_data = {}
        $scope.rest_map = [
            {"short" : "device", "url" : ICSW_URLS.REST_DEVICE_TREE_LIST, "options" : {"all_devices" : true, "ignore_cdg" : false, "tree_mode" : true, "ignore_disabled" : true}}
            {"short" : "device_group", "url" : ICSW_URLS.REST_DEVICE_GROUP_LIST}
            {"short" : "mother_server", "url" : ICSW_URLS.REST_DEVICE_TREE_LIST, "options" : {"all_mother_servers" : true}}
            {"short" : "monitor_server", "url" : ICSW_URLS.REST_DEVICE_TREE_LIST, "options" : {"monitor_server_type" : true}}
            {"short" : "domain_tree_node", "url" : ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST}
            {"short" : "device_sel", "url" : ICSW_URLS.REST_DEVICE_SELECTION_LIST}
        ]
        $scope.hide_list = [
            # short, full, default
            ["tln", "TLN", false, "Show top level node"]
            ["rrd_store", "RRD store", false, "Show if sensor data is store on disk"]
            ["passwd", "Password", false, "Show if a password is set"]
            ["mon_master", "MonMaster", false, "Show monitoring master"]
            ["boot_master", "BootMaster", false, "Show boot master"]
        ]
        $scope.column_list = [
            ['name', 'Name'],
            ['description', 'Description'],
            ['enabled', 'Enabled'],
            ['type', 'Type'],
        ].concat($scope.hide_list.map((elem) -> [elem[0], elem[1]]))

        $scope.num_shown = (exclude_list) ->
            exclude_list = exclude_list ? []
            return (entry for entry of $scope.hide_lut when $scope.hide_lut[entry] and entry not in exclude_list).length
        $scope.hide_lut = {}
        for entry in $scope.hide_list
            $scope.hide_lut[entry[0]] = entry[2]
        $scope.edit_map = {
            "device"       : "device.tree.form"
            "device_group" : "device.group.tree.form"
            "device_many"  : "device.tree.many.form"
        }
        $scope.modal_active = false
        $scope.entries = []
        $scope.$watch(
                () -> $scope.entries,
                () ->
                    $scope.entries_filtered = (entry for entry in $scope.entries when entry._show == true)
                true)
        $scope.new_devsel = (_dev_sel) ->
            $scope.sel_cache = _dev_sel
            $scope.initial_load = true
            $scope.reload()
        $scope.reload = (block_ui=true) ->
            if block_ui
                blockUI.start()
            # store selected state when not first load
            if not $scope.initial_load
                $scope.sel_cache = (entry.idx for entry in $scope.entries when entry.selected)
            wait_list = []
            for value, idx in $scope.rest_map
                $scope.rest_data[value.short] = restDataSource.reload([value.url, value.options])
                wait_list.push($scope.rest_data[value.short])
            $q.all(wait_list).then((data) ->
                for value, idx in data
                    if idx == 0
                        $scope.entries = value
                    $scope.rest_data[$scope.rest_map[idx].short] = value
                if block_ui
                    blockUI.stop()
                $scope.rest_data_set()
                $scope.update_entries_st_attrs()  # this depends on rest data
            )
        $scope.dg_present = () ->
            return (entry for entry in $scope.entries when entry.is_meta_device).length > 1
        $scope.modify = () ->
            if not $scope.form.$invalid
                rest_entry = (entry for entry in $scope.rest_map when entry.short == $scope._array_name)[0]
                if $scope.create_mode
                    Restangular.all(rest_entry["url"].slice(1)).post($scope.new_obj, rest_entry.options).then((new_data) ->
                        if $scope.new_obj.root_passwd
                            new_data.root_passwd_set = true
                        $scope.object_created(new_data)
                    )
                else
                    if $scope._array_name == "device"
                        cur_f = $scope.entries
                    else
                        cur_f = $scope.rest_data[$scope._array_name]
                    $scope.edit_obj.put(rest_entry.options).then(
                        (data) ->
                            $scope.my_modal.close()
                            icswTools.handle_reset(data, cur_f, $scope.edit_obj.idx)
                            if $scope.edit_obj.root_passwd
                                # hm, fixme
                                data.root_passwd_set = true
                                $scope.edit_obj.root_passwd_set = true
                            $scope.object_modified(data)
                        (resp) -> icswTools.handle_reset(resp.data, cur_f, $scope.edit_obj.idx)
                    )
            else
                toaster.pop("warning", "form validation problem", "", 0)
        $scope.form_error = (field_name) ->
            if $scope.form[field_name].$valid
                return ""
            else
                return "has-error"
        $scope.create = (a_name, event, parent_obj) ->
            $scope._array_name = a_name
            $scope.new_obj = $scope.new_object(a_name, parent_obj)
            $scope.create_or_edit(event, true, $scope.new_obj)
        $scope.edit = (a_name, event, obj) ->
            $scope._array_name = a_name
            $scope.pre_edit_obj = angular.copy(obj)
            $scope.create_or_edit(event, false, obj)
        $scope.create_or_edit = (event, create_or_edit, obj) ->
            $scope.edit_obj = obj
            #console.log $scope.edit_obj
            $scope.create_mode = create_or_edit
            $scope.edit_div = $compile($templateCache.get($scope.edit_map[$scope._array_name]))($scope)
            obj.root_passwd = ""
            $scope.my_modal = BootstrapDialog.show
                message: $scope.edit_div
                draggable: true
                size: BootstrapDialog.SIZE_WIDE
                cssClass: "modal-tall"
                closable: true
                closeByBackdrop: false
                onhidden: () =>
                    $scope.modal_active = false
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
                onshown: () =>
                    $scope.modal_active = true
        $scope.edit_many = (event) ->
            $scope._array_name = "device_many"
            edit_obj = {
                "many_form"          : true
                "device_group"       : (entry.idx for entry in $scope.rest_data.device_group when entry.cluster_device_group == false)[0]
                "domain_tree_node"   : (entry.idx for entry in $scope.rest_data.domain_tree_node when entry.depth == 0)[0]
                "root_passwd"        : ""
            }
            $scope.create_or_edit(event, false, edit_obj)
        $scope.modify_many = () ->
            #console.log "mm", $scope.edit_obj
            icswCallAjaxService
                url     : ICSW_URLS.DEVICE_CHANGE_DEVICES
                data    : {
                    "change_dict" : angular.toJson($scope.edit_obj)
                    "device_list" : angular.toJson((entry.idx for entry in $scope.entries when entry.is_meta_device == false and entry.selected))
                }
                success : (xml) ->
                    if icswParseXMLResponseService(xml)
                        if parseInt($(xml).find("value[name='changed']").text())
                            $scope.my_modal.close()
                            $scope.reload()
                            reload_sidebar_tree()
        $scope.delete = (a_name, obj) ->
            icswDialogDeleteObjects([obj], a_name, () -> $scope.reload(false))  # set blocking to false because it might happen in background of the delete dlg
        $scope.delete_many = (event) ->
            to_delete_list = (entry for entry in $scope.entries when entry.is_meta_device == false and entry.selected)
            icswDialogDeleteObjects(to_delete_list, "device", () -> $scope.reload(false)) # set blocking to false because it might happen in background of the delete dlg
        $scope.get_action_string = () ->
            return if $scope.create_mode then "Create" else "Modify"
        $scope.rest_data_set = () ->
            $scope.device_lut = icswTools.build_lut($scope.entries)
            $scope.device_group_lut = icswTools.build_lut($scope.rest_data.device_group)
            for entry in $scope.entries
                entry.selected = false
                entry.device_group_obj = $scope.device_group_lut[entry.device_group]
            mon_masters = (entry for entry in $scope.rest_data.monitor_server when entry.monitor_type == "master")
            if mon_masters.length
                $scope.mon_master = mon_masters[0].idx
            else
                $scope.mon_master = -1
            if $scope.initial_load
                # for initial load use device_sel as preselection
                $scope.sel_cache = (entry.idx for entry in $scope.rest_data["device_sel"] when entry.sel_type == "d")
            for pk in $scope.sel_cache
                if pk of $scope.device_lut
                    # ignore deleted devices
                    $scope.device_lut[pk].selected = true
            # monitor servers
            for entry in $scope.rest_data.monitor_server
                entry.full_name_wt = "#{entry.full_name} (#{entry.monitor_type})"
            $scope.initial_load = false
        $scope.num_selected = () ->
            if $scope.entries
                return (true for entry in $scope.entries when entry.selected and not entry.is_meta_device).length
            else
                return 0
        $scope.get_tr_class = (obj) ->
            return if obj.is_meta_device then "success" else ""
        $scope.ignore_md = (entry) ->
            return entry.identifier != "MD"
        $scope.ignore_cdg = (entry) ->
            return not entry.cluster_device_group
        $scope.object_modified = (mod_obj) ->
            mod_obj.selected = $scope.pre_edit_obj.selected
            mod_obj.device_group_obj = $scope.device_group_lut[mod_obj.device_group]
            if mod_obj.is_meta_device
                # copy enabled flag
                mod_obj.device_group_obj.enabled = mod_obj.enabled
            if mod_obj.device_group != $scope.pre_edit_obj.device_group
                # device group has changed, reload to fix all dependencies
                $scope.reload()
                reload_sidebar_tree()
        $scope.object_created = (new_obj) ->
            if $scope._array_name == "device"
                new_obj.selected = true
                md_obj = _.find($scope.entries, (obj) ->
                    return (obj.is_meta_device == true) and (obj.device_group == new_obj.device_group)
                )
                # hm, fishy code, sometimes strange behaviour
                $scope.entries.splice(_.indexOf($scope.entries, md_obj) + 1, 0, new_obj)
                $scope.device_lut[new_obj.idx] = new_obj
                $scope.device_group_lut[new_obj.device_group].num_devices++

                # increase postfix of device name
                node_re = new RegExp(/^(.*?)(\d+)(.*)$/)
                name_m = node_re.exec(new_obj.name)
                if name_m
                    new_name = ("0" for _idx in [0..name_m[2].length]).join("") + String(parseInt(name_m[2]) + 1)
                    $scope.edit_obj.name = name_m[1] + new_name.substr(new_name.length - name_m[2].length) + name_m[3]
                reload_sidebar_tree()
                $scope.update_entries_st_attrs()
            else if $scope._array_name == "device_group"
                # $scope.reload()
                reload_sidebar_tree()
        $scope.new_object = (a_name, parent_obj) ->
            new_obj = {
                "enabled" : true
                "enable_perfdata": true
                "store_rrd_data": true
                "flap_detection_enabled": true
            }
            if a_name == "device_group"
                new_obj.name = "nodes"
                new_obj.description = "new devicegroup"
                new_obj.domain_tree_node = (entry.idx for entry in $scope.rest_data.domain_tree_node when entry.depth == 0)[0]
            else
                new_obj.name = "dev"
                new_obj.comment = "new device"
                if parent_obj
                    new_obj.device_group = parent_obj.idx
                    new_obj.domain_tree_node = parent_obj.domain_tree_node
                else
                    new_obj.device_group = (entry.idx for entry in $scope.rest_data.device_group when entry.cluster_device_group == false)[0]
                    new_obj.domain_tree_node = (entry.idx for entry in $scope.rest_data.domain_tree_node when entry.depth == 0)[0]
            return new_obj
        $scope.update_selected = () ->
            icswCallAjaxService
                url     : ICSW_URLS.DEVICE_SET_SELECTION
                data    : {
                    "angular_sel" : angular.toJson((entry.idx for entry in $scope.entries when entry.selected))
                }
                success : (xml) ->
                    icswParseXMLResponseService(xml)

        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.new_devsel(args[0])
        )
        $scope.update_entries_st_attrs = () ->
            # use same keys as in $scope.column_list
            for obj in $scope.entries
                st_attrs = {}
                if obj.is_meta_device
                        # give some value, js sucks at comparing undefined
                        st_attrs['rrd_store'] = ""
                        st_attrs['passwd'] = ""
                        st_attrs['mon_master'] = ""
                        st_attrs['boot_master'] = ""
                        if obj.device_group_obj.cluster_device_group
                            new_el = $compile($templateCache.get("device_tree_cdg_row.html"))
                            st_attrs['name'] = obj.device_group_obj.name
                            st_attrs['description'] = obj.device_group_obj.description
                            st_attrs['enabled'] = null
                            st_attrs['type'] = null
                            st_attrs['tln'] = show_dtnFilter(array_lookupFilter(obj.device_group_obj.domain_tree_node, $scope.rest_data.domain_tree_node))
                        else
                            obj.device_group_obj.num_devices = (entry for entry in $scope.entries when entry.device_group == obj.device_group).length - 1
                            new_el = $compile($templateCache.get("device_tree_meta_row.html"))
                            st_attrs['name'] = obj.device_group_obj.name
                            st_attrs['description'] = obj.device_group_obj.description
                            st_attrs['enabled'] = obj.device_group_obj.enabled
                            st_attrs['type'] = obj.device_group_obj.num_devices
                            st_attrs['tln'] = show_dtnFilter(array_lookupFilter(obj.device_group_obj.domain_tree_node, $scope.rest_data.domain_tree_node))
                    else
                        new_el = $compile($templateCache.get("device_tree_row.html"))
                        st_attrs['name'] = obj.name
                        st_attrs['description'] = obj.comment
                        st_attrs['enabled'] = obj.enabled
                        st_attrs['tln'] = show_dtnFilter(array_lookupFilter(obj.domain_tree_node, $scope.rest_data.domain_tree_node))
                        st_attrs['rrd_store'] = obj.store_rrd_data
                        st_attrs['passwd'] = obj.root_passwd_set
                        st_attrs['mon_master'] = array_lookupFilter(obj.monitor_server, $scope.rest_data.monitor_server, "full_name_wt")
                        st_attrs['boot_master'] = array_lookupFilter(obj.bootserver, $scope.rest_data.mother_server, "full_name")
                obj.st_attrs = st_attrs
]).directive("icswDeviceTreeOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.tree.overview")
    }
]).directive("icswDeviceTreeRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            if scope.obj.is_meta_device
                if scope.obj.device_group_obj.cluster_device_group
                    new_el = $compile($templateCache.get("icsw.device.tree.cdg.row"))
                else
                    scope.obj.device_group_obj.num_devices = (entry for entry in scope.entries when entry.device_group == scope.obj.device_group).length - 1
                    new_el = $compile($templateCache.get("icsw.device.tree.meta.row"))
            else
                new_el = $compile($templateCache.get("icsw.device.tree.row"))
            scope.get_dev_sel_class = () ->
                if scope.obj.selected
                    return "btn btn-xs btn-success"
                else
                    return "btn btn-xs"
            scope.toggle_dev_sel = () ->
                scope.obj.selected = !scope.obj.selected
                scope.update_selected()
            scope.change_dg_sel = (flag) ->
                for entry in scope.entries
                    if entry.device_group == scope.obj.device_group
                        if flag == 1
                            entry.selected = true
                        else if flag == -1
                            entry.selected = false
                        else
                            entry.selected = not entry.selected
                scope.update_selected()
            element.append(new_el(scope))
    }
]).directive("icswDeviceTreeHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.tree.head")
    }
]).directive("icswDeviceTreeFilters", () ->
    # controller to set the _show flag of entries according to filters
    return {
        restrict : "E"
        templateUrl : "icsw.device.tree.filters"
        link : (scope, element, attrs) ->
            scope.filter_settings = {"dg_filter" : "b", "en_filter" : "b", "sel_filter" : "b", "mon_filter" : "i", "boot_filter" : "i"}

            filter_changed = () ->
                aft_dict = {
                    "b" : [true, false]
                    "f" : [false]
                    "t" : [true]
                }

                try
                    str_re = new RegExp(scope.filter_settings.str_filter, "gi")
                catch
                    str_re = new RegExp("^$", "gi")

                # meta device selection list
                md_list = aft_dict[scope.filter_settings.dg_filter]
                # enabled selection list
                en_list = aft_dict[scope.filter_settings.en_filter]
                # selected list
                sel_list = aft_dict[scope.filter_settings.sel_filter]
                for entry in scope.entries
                    if en_list.length == 2
                        # show all, no check
                        en_flag = true
                    else if en_list[0] == true
                        if entry.is_meta_device
                            en_flag = entry.device_group_obj.enabled
                        else
                            # show enabled (device AND device_group)
                            en_flag = entry.enabled and scope.device_group_lut[entry.device_group].enabled
                    else
                        if entry.is_meta_device
                            en_flag = not entry.device_group_obj.enabled
                        else
                            # show disabled (device OR device_group)
                            en_flag = not entry.enabled or (not scope.device_group_lut[entry.device_group].enabled)
                    # selected
                    sel_flag = entry.selected in sel_list
                    # monitoring
                    mon_f = scope.filter_settings.mon_filter
                    if mon_f == "i"
                        mon_flag = true
                    else
                        if entry.monitor_server == null
                            mon_flag = parseInt(mon_f) == scope.mon_master
                        else
                            mon_flag = parseInt(mon_f) == entry.monitor_server
                    boot_f = scope.filter_settings.boot_filter
                    boot_flag = (boot_f == "i") or (parseInt(boot_f) == entry.bootserver)

                    # string filter
                    if entry.is_meta_device
                        sf_flag = if (entry.name.match(str_re) or entry.comment.match(str_re)) then true else false
                    else
                        sf_flag = if (entry.full_name.match(str_re) or entry.comment.match(str_re)) then true else false

                    entry._show = (entry.is_meta_device in md_list) and en_flag and sel_flag and mon_flag and boot_flag and sf_flag


            scope.$watch(
                    () -> return scope.filter_settings
                    filter_changed
                    true)
            scope.$watch(
                    () -> scope.entries
                    filter_changed
                    true)

            scope.select_shown = () ->
                for entry in scope.entries
                    if not entry.is_meta_device
                        entry.selected = entry._show
            scope.deselect_all = () ->
                for entry in scope.entries
                    if not entry.is_meta_device
                        entry.selected = false
})
