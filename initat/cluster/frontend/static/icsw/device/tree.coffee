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

angular.module(
    "icsw.device.tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "smart-table",
        "icsw.tools.table", "icsw.tools", "icsw.tools.button", "icsw.tools.dialog",
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.devtree", {
            url: "/devtree"
            templateUrl: "icsw/main/device/tree.html"
            data:
                pageTitle: "Device tree"
                rights: ["user.modify_tree"]
                menuEntry:
                    menukey: "dev"
                    icon: "fa-list"
                    ordering: 15
        }
    )
]).controller("icswDeviceTreeCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",  "restDataSource", "$q", "$timeout", "icswComplexModalService",
    "$uibModal", "array_lookupFilter", "msgbus", "blockUI", "icswTools", "ICSW_URLS", "icswToolsButtonConfigService",
    "icswSimpleAjaxCall", "icswToolsSimpleModalService", "toaster", "icswDialogDeleteObjects", "icswDeviceBackup",
    "icswDeviceTreeService", "icswDomainTreeService", "ICSW_SIGNALS", "$rootScope", "icswActiveSelectionService", "icswDeviceGroupBackup",
(
    $scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $timeout, icswComplexModalService,
    $uibModal, array_lookupFilter, msgbus, blockUI, icswTools, ICSW_URLS, icswToolsButtonConfigService,
    icswSimpleAjaxCall, icswToolsSimpleModalService, toaster, icswDialogDeleteObjects, icswDeviceBackup,
    icswDeviceTreeService, icswDomainTreeService, ICSW_SIGNALS, $rootScope, icswActiveSelectionService, icswDeviceGroupBackup
) ->
    $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
    $scope.initial_load = true
    $scope.rest_data = {}
    $scope.rest_map = [
        # TODO: replace with specialized REST call
        {"short" : "mother_server", "url" : ICSW_URLS.REST_DEVICE_TREE_LIST, "options": {"all_mother_servers": true}}
        # TODO: replace with specialized REST call
        {"short" : "monitor_server", "url" : ICSW_URLS.REST_DEVICE_TREE_LIST, "options": {"monitor_server_type": true}}
    ]
    $scope.hide_list = [
        # short, full, default
        ["tln", "DTN", false, "Show top level node"]
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
    # hack, FIXME
    $scope.entries = []
    $scope.entries_filtered = []
    $scope.trigger_redraw = 0
    $scope.device_tree_valid = false

    $rootScope.$on(ICSW_SIGNALS("ICSW_DTREE_FILTER_CHANGED"), () ->
        $scope.update_filtered()
    )

    $scope.update_filtered = () ->
        # add search and filter fields
        $scope.update_entries_st_attrs()
        $scope.entries_filtered.length = 0
        for entry in $scope.device_tree.all_list
            if entry._show
                $scope.entries_filtered.push(entry)
        # force redraw
        $scope.trigger_redraw++
        console.log "length / filtered length: #{$scope.device_tree.all_list.length} / #{$scope.entries_filtered.length}"

    msgbus.emit("devselreceiver")

    msgbus.receive("devicelist", $scope, (name, args) ->
        $scope.new_devsel(args[0])
    )

    $scope.new_devsel = (_dev_sel) ->
        $scope.initial_load = true
        $scope.reload()

    $scope.reload = (block_ui=true) ->
        $scope.device_tree_valid = false
        if block_ui
            blockUI.start()
        wait_list = []
        # $scope.rest_data.mother_server = data[0]
        for value, idx in $scope.rest_map
            $scope.rest_data[value.short] = restDataSource.reload([value.url, value.options])
            wait_list.push($scope.rest_data[value.short])
        wait_list.push(icswDeviceTreeService.fetch($scope.$id))
        $q.all(wait_list).then(
            (data) ->
                $scope.device_tree_valid = true
                console.log "TreeData", data
                $scope.rest_data["mother_server"] = data[0]
                $scope.rest_data["monitor_server"] = data[1]
                $scope.device_tree = data[2]
                $scope.domain_tree = $scope.device_tree.domain_tree
                $scope.entries = $scope.device_tree.all_list
                if block_ui
                    blockUI.stop()
                $scope.rest_data_set()
                $scope.update_filtered()
        )
    $scope.dg_present = () ->
        # Todo, FIXME, make static
        return true
        return (entry for entry in $scope.device_tree.all_list when entry.is_meta_device).length > 1

    # device related calls

    $scope.create_device = (event, parent_obj) ->
        new_obj = {
            "enabled" : true
            "enable_perfdata": true
            "store_rrd_data": true
            "flap_detection_enabled": true
            "name": "dev"
            "comment": "new device"
        }
        if parent_obj
            new_obj.device_group = parent_obj.idx
            new_obj.domain_tree_node = parent_obj.domain_tree_node
        else
            new_obj.device_group = (entry.idx for entry in $scope.device_tree.group_list when entry.cluster_device_group == false)[0]
            new_obj.domain_tree_node = (entry.idx for entry in $scope.domain_tree when entry.depth == 0)[0]
        $scope.create_or_edit(event, true, new_obj, true, false)

    $scope.edit_device = (event, obj) ->
        $scope.create_or_edit(event, false, obj, true, false)

    $scope.delete_device = (obj) ->
        icswDialogDeleteObjects(
            [obj]
            "device"
            (arg) ->
                console.log "after device delete", arg
                if arg?
                    $scope.handle_device_delete(arg.del_pks)
        )

    $scope.handle_device_delete = (pks) ->
        for pk in pks
            $scope.device_tree.delete_device(pk)
        $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))

    # device group related calls

    $scope.create_device_group = (event) ->
        new_obj = {
            "enabled" : true
            "name": "nodes"
            "description": "new devicegroup"
            "domain_tree_node": (entry.idx for entry in $scope.domain_tree when entry.depth == 0)[0]
        }
        $scope.create_or_edit(event, true, new_obj, true, true)

    $scope.edit_device_group = (event, obj) ->
        $scope.create_or_edit(event, false, obj, true, true)

    $scope.delete_device_group = (obj) ->
        icswDialogDeleteObjects(
            [obj]
            "device_group"
            (arg) ->
                console.log "after device_group delete", arg
                if arg?
                    $scope.handle_device_group_delete(arg.del_pks)
        )

    $scope.handle_device_group_delete = (pks) ->
        for pk in pks
            $scope.device_tree.delete_device_group(pk)
        $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))

    # many device edit

    $scope.edit_many = (event) ->
        $scope._array_name = "device_many"
        edit_obj = {
            "many_form"          : true
            "device_group"       : (entry.idx for entry in $scope.device_tree.group_list when entry.cluster_device_group == false)[0]
            "domain_tree_node"   : (entry.idx for entry in $scope.domain_tree when entry.depth == 0)[0]
            "root_passwd"        : ""
        }
        $scope.create_or_edit(event, false, edit_obj, false, false)

    $scope.delete_many = (event) ->
        sel_list = icswActiveSelectionService.current().get_devsel_list()[1]
        to_delete_list = (entry for entry in $scope.device_tree.all_list when entry.is_meta_device == false and entry.idx in sel_list)
        icswDialogDeleteObjects(
            to_delete_list
            "device"
            (arg) ->
                console.log "after man device delete", arg
                if arg?
                    $scope.handle_device_delete(arg.del_pks)
        )

    $scope.create_or_edit = (event, create_mode, obj, single_instance, is_group) ->
        if single_instance
            if is_group
                dbu = new icswDeviceGroupBackup()
            else
                dbu = new icswDeviceBackup()
            dbu.create_backup(obj)
        $scope.edit_obj = obj
        obj.root_passwd = ""
        # which template to use
        if is_group
            template_name = "device.group.tree.form"
        else if single_instance
            template_name = "device.tree.form"
        else
            template_name = "device.tree.many.form"
        # init form
        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))($scope)
                ok_label: if create_mode then "Create" else "Modify"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if $scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        if create_mode
                            if is_group
                                $scope.device_tree.create_device_group($scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("device_group created")
                                    (notok) ->
                                        d.reject("device_group not created")
                                )
                            else
                                $scope.device_tree.create_device($scope.edit_obj).then(
                                    (ok) ->
                                        # device createed, force refiltering
                                        $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
                                        # rewrite name for next device
                                        node_re = new RegExp(/^(.*?)(\d+)(.*)$/)
                                        name_m = node_re.exec(obj.name)
                                        if name_m
                                            new_name = ("0" for _idx in [0..name_m[2].length]).join("") + String(parseInt(name_m[2]) + 1)
                                            $scope.edit_obj.name = name_m[1] + new_name.substr(new_name.length - name_m[2].length) + name_m[3]
                                        d.reject("device created")
                                    (notok) ->
                                        d.reject("device not created")
                                )
                        else
                            if single_instance
                                $scope.edit_obj.put().then(
                                    (data) ->
                                        # ToDo, FIXME, handle change (test?), move to DeviceTreeService
                                        # icswTools.handle_reset(data, cur_f, $scope.edit_obj.idx)
                                        console.log "data", data
                                        if $scope.edit_obj.root_passwd
                                            # ToDo, FIXME, to be improved
                                            $scope.edit_obj.root_passwd_set = true
                                        d.resolve("save")
                                        # update device ordering in tree
                                        $scope.device_tree.reorder()
                                    (reject) ->
                                        # ToDo, FIXME, handle rest (test?)
                                        # icswTools.handle_reset(resp.data, cur_f, $scope.edit_obj.idx)
                                        # two possibilites: restore and continue or reject, right now we use the second path
                                        # dbu.restore_backup(obj)
                                        d.reject("not saved")
                                )
                            else
                                # multi instance modify
                                icswSimpleAjaxCall(
                                    url     : ICSW_URLS.DEVICE_CHANGE_DEVICES
                                    data    : {
                                        "change_dict" : angular.toJson($scope.edit_obj)
                                        "device_list" : angular.toJson(icswActiveSelectionService.current().get_devsel_list()[1])
                                    }
                                ).then(
                                    (xml) ->
                                        changes = angular.fromJson($(xml).find("value[name='json_changes']").text())
                                        $scope.device_tree.apply_json_changes(changes)
                                        d.resolve("many changed")
                                )
                    return d.promise
                cancel_callback: (modal) ->
                    if single_instance
                        dbu.restore_backup(obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "DeviceTree requester closed, trigger redraw"
                # trigger refiltering of list
                $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
        )

    $scope.rest_data_set = () ->
        # $scope.device_lut = icswTools.build_lut($scope.entries)
        # $scope.device_group_lut = icswTools.build_lut($scope.rest_data.device_group)
        # for entry in $scope.entries
        #     entry.selected = false
        #    entry.device_group_obj = $scope.device_group_lut[entry.device_group]
        mon_masters = (entry for entry in $scope.rest_data.monitor_server when entry.monitor_type == "master")
        if mon_masters.length
            $scope.mon_master = mon_masters[0].idx
        else
            $scope.mon_master = -1
        # monitor servers
        for entry in $scope.rest_data.monitor_server
            entry.full_name_wt = "#{entry.full_name} (#{entry.monitor_type})"
        $scope.initial_load = false

    $scope.num_selected = () ->
        act_sel = icswActiveSelectionService.get_selection()
        return act_sel.tot_dev_sel.length

    $scope.get_tr_class = (obj) ->
        return if obj.is_meta_device then "success" else ""

    $scope.ignore_md = (entry) ->
        return entry.identifier != "MD"

    $scope.ignore_cdg = (group) ->
        return not group.cluster_device_group

    $scope.update_entries_st_attrs = () ->
        # use same keys as in $scope.column_list
        # create sort entries
        for obj in $scope.device_tree.all_list
            group = $scope.device_tree.get_group(obj)
            st_attrs = {}
            if obj.is_meta_device
                # give some value, js sucks at comparing undefined
                st_attrs['rrd_store'] = ""
                st_attrs['passwd'] = ""
                st_attrs['mon_master'] = ""
                st_attrs['boot_master'] = ""
                st_attrs['name'] = group.name
                st_attrs['description'] = group.description
                if $scope.device_tree.get_meta_device(obj).is_cluster_device_group
                    st_attrs['enabled'] = null
                    st_attrs['type'] = null
                else
                    st_attrs['enabled'] = group.enabled
                    # do not count the meta device
                    st_attrs['type'] = obj.num_devices
                st_attrs['tln'] = $scope.domain_tree.show_dtn(group)
            else
                st_attrs['name'] = obj.name
                st_attrs['description'] = obj.comment
                st_attrs['enabled'] = obj.enabled
                st_attrs['tln'] = $scope.domain_tree.show_dtn(obj)
                st_attrs['rrd_store'] = obj.store_rrd_data
                st_attrs['passwd'] = obj.root_passwd_set
                st_attrs['mon_master'] = array_lookupFilter(obj.monitor_server, $scope.rest_data.monitor_server, "full_name_wt")
                st_attrs['boot_master'] = array_lookupFilter(obj.bootserver, $scope.rest_data.mother_server, "full_name")
            obj.st_attrs = st_attrs
    $scope.reload()
]).directive("icswDeviceTreeOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.tree.overview")
    }
]).directive("icswDeviceTreeRow", ["$templateCache", "$compile", "icswActiveSelectionService", "icswDeviceTreeService", ($templateCache, $compile, icswActiveSelectionService, icswDeviceTreeService) ->
    return {
        restrict : "EA"
        link : (scope, element, attrs) ->
            tree = icswDeviceTreeService.current()
            device = scope.$eval(attrs.device)
            group = tree.get_group(device)
            scope.device = device
            scope.group = group
            sel = icswActiveSelectionService.current()
            if device.is_meta_device
                if scope.device_tree.get_group(device).cluster_device_group
                    new_el = $compile($templateCache.get("icsw.device.tree.cdg.row"))
                else
                    new_el = $compile($templateCache.get("icsw.device.tree.meta.row"))
            else
                new_el = $compile($templateCache.get("icsw.device.tree.row"))
            scope.get_dev_sel_class = () ->
                if sel.device_is_selected(device)
                    return "btn btn-xs btn-success"
                else
                    return "btn btn-xs"
            scope.toggle_dev_sel = () ->
                sel.toggle_selection(device)
            scope.change_dg_sel = (flag) ->
                tree = icswDeviceTreeService.current()
                for entry in tree.all_list
                    if entry.device_group == device.device_group
                        if flag == 1
                            sel.add_selection(entry)
                        else if flag == -1
                            sel.remove_selection(entry)
                        else
                            sel.toggle_selection(entry)
            element.append(new_el(scope))
    }
]).directive("icswDeviceTreeHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.tree.head")
    }
]).directive("icswDeviceTreeFilters", ["icswDeviceTreeService", "icswActiveSelectionService", "ICSW_SIGNALS", "$rootScope", (icswDeviceTreeService, icswActiveSelectionService, ICSW_SIGNALS, $rootScope) ->
    # controller to set the _show flag of entries according to filters
    return {
        restrict : "E"
        templateUrl : "icsw.device.tree.filters"
        link : (scope, element, attrs) ->
            scope.filter_settings = {
                "dg_filter" : "b"
                "en_filter" : "b"
                "sel_filter" : "b"
                "mon_filter" : "i"
                "boot_filter" : "i"
            }

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
                devtree = icswDeviceTreeService.current()
                act_sel = icswActiveSelectionService.get_selection()
                for entry in devtree.all_list
                    if en_list.length == 2
                        # show all, no check
                        en_flag = true
                    else if en_list[0] == true
                        if entry.is_meta_device
                            en_flag = devtree.get_group(entry).enabled
                        else
                            # show enabled (device AND device_group)
                            en_flag = entry.enabled and devtree.get_group(entry).enabled
                    else
                        if entry.is_meta_device
                            en_flag = not devtree.get_group(entry).enabled
                        else
                            # show disabled (device OR device_group)
                            en_flag = not entry.enabled or (not devtree.get_group(entry).enabled)
                    # selected
                    selected = entry.idx of act_sel.tot_dev_sel
                    sel_flag = selected in sel_list
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
                $rootScope.$emit(ICSW_SIGNALS("ICSW_DTREE_FILTER_CHANGED"))

            scope.$watch(
                () ->
                    scope.filter_settings
                () ->
                    filter_changed()
                true
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_TREE_LOADED"), () ->
                filter_changed()
            )

            $rootScope.$on(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"), () ->
                filter_changed()
            )

            scope.select_shown = () ->
                devtree = icswDeviceTreeService.current()
                act_sel = icswActiveSelectionService.get_selection()
                for entry in devtree.all_list
                    if not entry.is_meta_device
                        if entry._show
                            act_sel.add_selection(entry)
                        else
                            act_sel.remove_selection(entry)
            scope.deselect_all = () ->
                icswActiveSelectionService.get_selection().deselect_all_devices()
    }
])
