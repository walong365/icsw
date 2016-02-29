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
    "icsw.layout.selection",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.tools.tree", "icsw.user",
    ]
).service("icswBackupDefinition", [() ->
    class backup_def
        constructor: () ->
            @simple_attributes = []
            @list_attributes = []
        create_backup: (obj) =>
            _bu = {}
            @pre_backup(obj)
            for _entry in @simple_attributes
                _bu[_entry] = obj[_entry]
            for _entry in @list_attributes
                _bu[_entry] = _.cloneDeep(obj[_entry])
            @post_backup(obj, _bu)
            obj._ICSW_backup = _bu
        restore_backup: (obj) =>
            if obj._ICSW_backup?
                _bu = obj._ICSW_backup
                @pre_restore(obj, _bu)
                for _entry in @simple_attributes
                    obj[_entry] = _bu[_entry]
                for _entry in @list_attributes
                    obj[_entry] = _.cloneDeep(_bu[_entry])
                @post_restore(obj, _bu)
                delete obj._ICSW_backup
        pre_backup: (obj) =>
            # called before backup
        post_backup: (obj, bu) =>
            # called after backuop
        pre_restore: (obj, bu) =>
            # called before restore
        post_restore: (obj, bu) =>
            # called after restore

]).service("icswDeviceBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = [
                "name", "comment", "device_group", "domain_tree_node", "enabled",
                "alias", "mon_device_templ", "monitor_checks", "enable_perfdata",
                "flap_detection_enabled", "mon_resolve_name", "store_rrd_data"
            ]

]).service("icswDeviceGroupBackup", ["icswBackupDefinition", (icswBackupDefinition) ->

    class icswDeviceGroupBackupDefinition extends icswBackupDefinition

        constructor: () ->
            super()
            @simple_attributes = ["name", "comment", "domain_tree_node", "enabled"]

]).service("icswEnrichmentInfo", [() ->
    # stores info about already fetched additional info from server
    class icswEnrichmentInfo
        constructor: (@device) ->
            # device may be the device_tree for global instance
            @loaded = []

        is_scalar: (req) =>
            return req in ["disk_info", "snmp_info"]

        get_attr_name: (req) =>
            _lut = {
                "network_info": "netdevice_set"
                "monitoring_hint_info": "monitoring_hint_set"
                "disk_info": "act_partition_table"
                "com_info": "com_capability_list"
                "snmp_info": "devicesnmpinfo"
                "snmp_schemes_info": "snmp_schemes"
            }
            if req of _lut
                return _lut[req]
            else
                throw new Error("Unknown EnrichmentKey #{req}")

        clear_infos: (req_list) =>
            # clear already present infos
            for req in req_list
                if @is_scalar(req)
                    @device[@get_attr_name(req)] = undefined
                else
                    @device[@get_attr_name(req)].length = 0

        build_request: (req_list) =>
            # returns a list (dev_pk, enrichments_to_load)
            fetch_list = []
            for req in req_list
                if req not in @loaded
                    fetch_list.push(req)
                    if @is_scalar(req)
                        @device[@get_attr_name(req)] = undefined
                    else
                        @device[@get_attr_name(req)] = []
            return [@device.idx, fetch_list]

        feed_result: (key, result) =>
            if key not in @loaded
                @loaded.push(key)
            # store info
            if @is_scalar(key)
                @device[@get_attr_name(key)] = result
            else
                @device[@get_attr_name(key)].push(result)

        merge_requests: (req_list) =>
            # merges all requests from build_request
            to_load = {}
            for d_req in req_list
                for req in d_req[1]
                    if req not of to_load
                        to_load[req] = []
                    to_load[req].push(d_req[0])
            return to_load

        feed_results: (result) =>
            # feed result into device_tree
            for key, obj_list of result
                for obj in obj_list
                    if obj.device?
                        _pk = obj.device
                        @device.all_lut[_pk].$$_enrichment_info.feed_result(key, obj)
                    else
                        console.log obj
                        throw new Error("No device attribute found in object")

]).service("icswDeviceTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "icswEnrichmentInfo", "icswSimpleAjaxCall",
(
    icswTools, ICSW_URLS, $q, Restangular, icswEnrichmentInfo, icswSimpleAjaxCall
) ->
    class icswDeviceTree
        constructor: (full_list, cat_list, group_list, domain_tree) ->
            @cat_list = cat_list
            @group_list = group_list
            @all_list = []
            @enabled_list = []
            @disabled_list = []
            @domain_tree = domain_tree
            @enricher = new icswEnrichmentInfo(@)
            @build_luts(full_list)

        reorder: () =>
            # device/group names or device <-> group relationships might have changed, sort
            for dev in @all_list
                group = @group_lut[dev.device_group]
                dev.device_group_name = group.name
                dev._nc_device_group_name = _.toLower(dev.device_group_name)
                dev.full_name = @domain_tree.get_full_name(dev)
                dev._nc_name = _.toLower(dev.name)
            # see code in rest_views
            @build_luts(
                _.orderBy(
                    @all_list
                    ["is_cluster_device_group", "_nc_device_group_name", "is_meta_device", "_nc_name"]
                    ["desc", "asc", "desc", "asc"]
                )
            )

        build_luts: (full_list) =>
            console.log (entry.name for entry in full_list)
            # build luts and create enabled / disabled lists
            @all_list.length = 0
            @enabled_list.length = 0
            @disabled_list.length = 0
            @enabled_lut = {}
            @disabled_lut = {}
            _disabled_groups = []
            for _entry in full_list
                @all_list.push(_entry)
                if not _entry.is_meta_device and _entry.device_group in _disabled_groups
                    @disabled_list.push(_entry)
                else if _entry.enabled
                    @enabled_list.push(_entry)
                else
                    if _entry.is_meta_device
                        _disabled_groups.push(_entry.device_group)
                    @disabled_list.push(_entry)
            @enabled_lut = icswTools.build_lut(@enabled_list)
            @disabled_lut = icswTools.build_lut(@disabled_list)
            @all_lut = icswTools.build_lut(@all_list)
            @group_lut = icswTools.build_lut(@group_list)
            @cat_lut = icswTools.build_lut(@cat_list)
            # console.log @enabled_list.length, @disabled_list.length, @all_list.length
            @link()

        link: () =>
            # create links between groups and devices
            for group in @group_list
                # reference to all devices
                group.devices = []
            for cat in @cat_list
                cat.devices = []
            for entry in @all_list
                # add enrichment info
                if not entry.$$_enrichment_info?
                    entry.$$_enrichment_info = new icswEnrichmentInfo(entry)
                # do not set group here to prevent circular dependencies in serializer
                # entry.group_object = @group_lut[entry.device_group]
                @group_lut[entry.device_group].devices.push(entry.idx)
                for cat in entry.categories
                    @cat_lut[cat].devices.push(entry.idx)
            for group in @group_list
                # num of all devices (enabled and disabled, also with md)
                group.num_devices_with_meta = group.devices.length
                group.num_devices = group.num_devices_with_meta - 1
            # create helper structures
            # console.log "link"

        get_meta_device: (dev) =>
            return @all_lut[@group_lut[dev.device_group].device]

        ignore_cdg: (group) =>
            # return true when group is not the CDG
            return !group.cluster_device_group

        get_group: (dev) =>
            return @group_lut[dev.device_group]

        get_category: (cat) =>
            return @cat_lut[cat]

        get_num_devices: (group) =>
            # return all enabled devices in group, not working ... ?
            console.log("DO NOT USE: get_num_devices()")
            return (entry for entry in @enabled_list when entry.device_group == group.idx).length - 1

        create_device_group: (new_dg) =>
            # create new device_group
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DEVICE_GROUP_LIST.slice(1)).post(new_dg).then(
                (new_obj) =>
                    # add new device_group to group_list
                    @group_list.push(new_obj)
                    # update group_lut
                    @group_lut[new_obj.idx] = new_obj
                    # fetch corresponding meta_device
                    @_fetch_device(new_obj.device, defer, "created device_group")
                (not_ok) ->
                    defer.reject("not created")
            )
            return defer.promise

        delete_device_group: (dg_pk) =>
            group = @group_lut[dg_pk]
            _.remove(@all_list, (entry) -> return entry.idx == group.device)
            _.remove(@group_list, (entry) -> return entry.idx == dg_pk)
            @reorder()

        create_device: (new_dev) =>
            # create new device
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).post(new_dev).then(
                (new_obj) =>
                    @_fetch_device(new_obj.idx, defer, "created device")
                (not_ok) ->
                    defer.object("not created")
            )
            return defer.promise

        delete_device: (d_pk) =>
            _.remove(@all_list, (entry) -> return entry.idx == d_pk)
            @reorder()

        _fetch_device: (pk, defer, msg) =>
            Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList(
                {
                    "ignore_cdg": false
                    "tree_mode" : true
                    "with_categories" : true
                    "ignore_disabled": true
                    "pks": angular.toJson([pk])
                }
            ).then(
                (dev_list) =>
                    dev = dev_list[0]
                    @all_list.push(dev)
                    @reorder()
                    defer.resolve(msg)
            )

        apply_json_changes: (json) =>
            # apply changes from json changedict
            for entry in json
                dev = @all_lut[entry.device]
                dev[entry.attribute] = entry.value
            @reorder()

        # enrichment functions
        enrich_devices: (dev_list, en_list) =>
            defer  = $q.defer()
            # build request
            en_req = @enricher.merge_requests(
                (
                    dev.$$_enrichment_info.build_request(en_list) for dev in dev_list
                )
            )
            icswSimpleAjaxCall(
                "url": ICSW_URLS.DEVICE_ENRICH_DEVICES
                "data": {
                    "enrich_request": angular.toJson(en_req)
                }
                dataType: "json"
            ).then(
                (result) =>
                    # clear previous values
                    console.log "clear previous enrichment values"
                    (dev.$$_enrichment_info.clear_infos(en_list) for dev in dev_list)
                    console.log "set new enrichment values"
                    @enricher.feed_results(result)
                    # resolve with device list
                    defer.resolve(dev_list)
            )
            return defer.promise

]).service("icswDeviceTreeService", ["$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools", "icswDeviceTree", "$rootScope", "ICSW_SIGNALS", "icswDomainTreeService", ($q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools, icswDeviceTree, $rootScope, ICSW_SIGNALS, icswDomainTreeService) ->
    rest_map = [
        [
            ICSW_URLS.REST_DEVICE_TREE_LIST
            {
                "ignore_cdg" : false
                "tree_mode" : true
                "all_devices" : true
                "with_categories" : true
                "ignore_disabled": true
            }
        ]
        [
            ICSW_URLS.REST_CATEGORY_LIST
            {}
        ]
        [
            ICSW_URLS.REST_DEVICE_GROUP_LIST
            {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false
    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(icswDomainTreeService.fetch(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** device tree loaded ***"
                _result = new icswDeviceTree(data[0], data[1], data[2], data[3])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_TREE_LOADED"), _result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer
    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]
    return {
        "load": (client) ->
            # loads from server
            return load_data(client).promise
        "fetch": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "current": () ->
            return _result
    }
]).service("icswSelectionGetDeviceService", ["icswDeviceTreeService", "$q", (icswDeviceTreeService, $q) ->
    id = Math.random()
    return (dev_pk) ->
        defer = $q.defer()
        icswDeviceTreeService.fetch(id).then((new_data) ->
            if dev_pk of new_data.all_lut
                defer.resolve(new_data.all_lut[dev_pk])
            else
                defer.resolve(undefined)
        )
        return defer.promise
]).service("icswSelectionDeviceExists", ["icswDeviceTreeService", "$q", (icswDeviceTreeService, $q) ->
    id = Math.random()
    return (dev_pk) ->
        defer = $q.defer()
        icswDeviceTreeService.fetch(id).then((new_data) ->
            defer.resolve(dev_pk of new_data.all_lut)
        )
        return defer.promise
]).service("icswActiveSelectionService", ["$q", "Restangular", "msgbus", "$rootScope", "ICSW_URLS", "icswSelection",  "ICSW_SIGNALS", ($q, Restangular, msgbus, $rootScope, ICSW_URLS, icswSelection, ICSW_SIGNALS) ->
    # used by menu.coffee (menu_base)
    _receivers = 0
    cur_selection = new icswSelection([], [], [], [])
    msgbus.receive("devselreceiver", $rootScope, (name, args) ->
        # args is an optional sender name to find errors
        console.log "ignore old devselreciever"
        # _receivers += 1
        # console.log "register dsr"
        # $rootScope.$emit(ICSW_SIGNALS("ICSW_DSR_REGISTERED"))
        # send_selection()
    )
    register_receiver = () ->
        _receivers += 1
        console.log "registered receiver"
        $rootScope.$emit(ICSW_SIGNALS("ICSW_DSR_REGISTERED"))
        send_selection()
    sync_selection = (new_sel) ->
        cur_selection.update(new_sel.categories, new_sel.device_groups, new_sel.devices, [])
        cur_selection.sync_with_db(new_sel)
    unsync_selection = () ->
        cur_selection.sync_with_db(undefined)
    send_selection = () ->
        console.log "emit current device selection"
        $rootScope.$emit(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION"))
        # msgbus.emit("devicelist", )
    return {
        "num_receivers": () ->
            return _receivers
        "current": () ->
            return cur_selection
        "get_selection": () ->
            return cur_selection
        "sync_selection": (new_sel) ->
            # synchronizes cur_selection with new_sel
            sync_selection(new_sel)
        "unsync_selection": () ->
            # remove synchronization with saved (==DB-selection)
            unsync_selection()
        "send_selection": () ->
            send_selection()
        "register_receiver": () ->
            register_receiver()
    }
]).service("icswSelection", ["icswDeviceTreeService", "$q", "icswSimpleAjaxCall", "ICSW_URLS", "$rootScope", "Restangular", "icswSavedSelectionService", "ICSW_SIGNALS", (icswDeviceTreeService, $q, icswSimpleAjaxCall, ICSW_URLS, $rootScope, Restangular, icswSavedSelectionService, ICSW_SIGNALS) ->
    class Selection
        # only instantiated once (for now), also handles saved selections
        constructor: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->
            $rootScope.$on(ICSW_SIGNALS("ICSW_TREE_LOADED"), (event, tree) =>
                @tree = tree
                console.log "tree set for icswSelection", @tree
            )
            @tree = undefined
            @sync_with_db(undefined)
        update: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->
        sync_with_db: (@db_obj=undefined) =>
            if @db_obj
                @db_idx = @db_obj.idx
                @cat_sel_db = angular.copy(@cat_sel)
                @devg_sel_db = angular.copy(@devg_sel)
                @dev_sel_db = angular.copy(@dev_sel)
                # selection has changed
                @changed = false
                @compare_with_db()
            else
                # unsync
                @db_idx = 0
                delete @cat_sel_db
                delete @devg_sel_db
                delete @dev_sel_db
                @db_obj = {
                    "info": ""
                    "name": "New selection"
                }
                # is disabled on the drop-down selection list
                # selection has changed, dummy flag, should never be used
                @changed = true
        compare_with_db: () =>
            @changed = false
            # compare current selection with _db instances
            for _entry in ["cat_sel", "devg_sel", "dev_sel"]
                _db_entry = "#{_entry}_db"
                if _.sum(@[_entry]) != _.sum(@[_db_entry]) or @[_entry].length != @[_db_entry].length
                    @changed = true
            @create_info()
        create_info: () =>
            icswSavedSelectionService.enrich_selection(@db_obj)
            if @changed
                @db_obj.info = "(*) #{@db_obj.info}"

        toggle_selection: (obj) =>
            # toggle selection of object
            _selected = obj.idx in @dev_sel
            if _selected
                @remove_selection(obj)
            else
                @add_selection(obj)

        add_selection: (obj) =>
            # add selection
            if obj.idx not in @dev_sel
                @dev_sel.push(obj.idx)
                @tot_dev_sel.push(obj.idx)

        remove_selection: (obj) =>
            # remove selection
            if obj.idx in @dev_sel
                _.pull(@dev_sel, obj.idx)
                _.pull(@tot_dev_sel, obj.idx)

        device_is_selected: (obj) =>
            # only works for devices
            return obj.idx in @dev_sel

        deselect_all_devices: (obj) =>
            @dev_sel = []
            @tot_dev_sel = []

        selection_saved: () =>
            # database object saved
            console.log "resync", @db_obj
            @sync_with_db(@db_obj)

        is_synced: () =>
            return if @db_idx then true else false

        any_selected: () ->
            return if @cat_sel.length + @devg_sel.length + @dev_sel.length + @tot_dev_sel.length then true else false

        any_lazy_selected: () ->
            return if @cat_sel.length + @devg_sel.length then true else false

        resolve_lazy_selection: () ->
            # categories
            for _cat in @cat_sel
                for _cs in @tree.cat_lut[_cat].devices
                    @tot_dev_sel.push(_cs)
            @cat_sel = []
            # groups
            for _group in @devg_sel
                for _gs in @tree.group_lut[_group].devices
                    @dev_sel.push(_gs)
                    @tot_dev_sel.push(_gs)
            @devg_sel = []
            @tot_dev_sel = _.uniq(@tot_dev_sel)
            @dev_sel = _.uniq(@dev_sel)

        resolve_dev_name: (dev_idx) =>
            _dev = @tree.all_lut[dev_idx]
            if _dev.is_meta_device
                return "[M] " + _dev.full_name.substring(8)
            else
                return _dev.full_name

        resolve_devices: () =>
            if @dev_sel.length
                _list = ((@resolve_dev_name(_ds) for _ds in @dev_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        resolve_total_devices: () =>
            if @tot_dev_sel.length
                _list = ((@resolve_dev_name(_ds) for _ds in @tot_dev_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        resolve_device_groups: () =>
            if @devg_sel.length
                _list = (@tree.group_lut[_dg].name.substring(8) for _dg in @devg_sel)
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        resolve_categories: () ->
            if @cat_sel.length
                _list = ((@tree.cat_lut[_cs].full_name for _cs in @cat_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        get_devsel_list: () =>
            # all device pks
            dev_pk_list = @tot_dev_sel
            # all non-meta device pks
            dev_pk_nmd_list = []
            # all device_group pks
            devg_pk_list = []
            # all meta device pks
            dev_pk_md_list = []
            for _pk in @tot_dev_sel
                _dev = @tree.all_lut[_pk]
                if _dev
                    if _dev.is_meta_device
                        devg_pk_list.push(_dev.device_group)
                        dev_pk_md_list.push(_pk)
                    else
                        dev_pk_nmd_list.push(_pk)
                else
                    console.log "device with pk #{_pk} is not resolvable"
            return [dev_pk_list, dev_pk_nmd_list, devg_pk_list, dev_pk_md_list]

        category_selected: (cat_idx) ->
            return cat_idx in @cat_sel

        device_group_selected: (devg_idx) ->
            return devg_idx in @devg_sel

        device_selected: (dev_idx) ->
            if dev_idx in @dev_sel or dev_idx in @tot_dev_sel
                return true
            else
                return false
        save_db_obj: () =>
            if @db_obj
                console.log @db_obj
                console.log @dev_sel
                @db_obj.categories = (entry for entry in @cat_sel)
                @db_obj.device_groups = (entry for entry in @devg_sel)
                @db_obj.devices = (entry for entry in @dev_sel)
                console.log @db_obj
                @db_obj.put().then(
                    (old_obj) =>
                        @selection_saved()
                )
        create_saved_selection: (user) =>
            defer = $q.defer()
            _sel = {
                "name": @db_obj.name
                "user": user.idx
                "devices": @dev_sel
                "categories": @cat_sel
                "device_groups": @devg_sel
            }
            # console.log "save", _sel
            Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).post(_sel).then(
                (data) =>
                    # enrich_selection(data)
                    @sync_with_db(data)
                    defer.resolve(data)
            )
            return defer.promise

        delete_saved_selection: () =>
            defer = $q.defer()
            @db_obj.remove().then(
                () =>
                    @sync_with_db(undefined)
                    defer.resolve(true)
            )
            return defer.promise

        select_parent: () ->
            defer = $q.defer()
            icswSimpleAjaxCall(
                "url": ICSW_URLS.DEVICE_SELECT_PARENTS
                "data": {
                    "angular_sel" : angular.toJson(@tot_dev_sel)
                }
                dataType: "json"
            ).then(
                (data) =>
                    @tot_dev_sel = data["new_selection"]
                    defer.resolve(data)
            )
            return defer.promise

]).service("icswSavedSelectionService", ["Restangular", "$q", "ICSW_URLS", "icswUserService", (Restangular, $q, ICSW_URLS, icswUserService) ->
    enrich_selection = (entry) ->
        _created = moment(entry.date)
        info = [entry.name]
        if entry.devices.length
            info.push("#{entry.devices.length} devs")
        if entry.device_groups.length
            info.push("#{entry.device_groups.length} groups")
        if entry.categories.length
            info.push("#{entry.categories.length} cats")
        info = info.join(", ")
        info = "#{info} (#{_created.format('YYYY-MM-DD HH:mm')})"
        entry.info = info
    _list = []
    load_selections = () ->
        defer = $q.defer()
        icswUserService.load().then(
            (user) ->
                Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).getList({"user": user.idx}).then(
                    (data) ->
                        (enrich_selection(entry) for entry in data)
                        _list = data
                        defer.resolve(_list)
                )
        )
        return defer.promise
    save_selection = (user, sel) ->
        defer = $q.defer()
        sel.create_saved_selection(user).then(
            (data) ->
                enrich_selection(data)
                _list.push(data)
                defer.resolve(data)
        )
        return defer.promise
    delete_selection = (sel) ->
        defer = $q.defer()
        del_id = sel.db_idx
        sel.delete_saved_selection().then(
            () ->
                console.log del_id, (entry.idx for entry in _list)
                _list = (entry for entry in _list when entry.idx != del_id)
                defer.resolve(_list)
        )
        return defer.promise
    return {
        "load_selections": () ->
            return load_selections()
        "save_selection": (user, sel) ->
            return save_selection(user, sel)
        "delete_selection": (sel) ->
            return delete_selection(sel)
        "enrich_selection": (obj) ->
            enrich_selection(obj)
    }
]).controller("icswLayoutSelectionController",
[
    "$scope", "icswLayoutSelectionTreeService", "$timeout", "icswDeviceTreeService", "ICSW_SIGNALS",
    "icswSelection", "icswActiveSelectionService", "$q", "icswSavedSelectionService", "icswToolsSimpleModalService",
    "DeviceOverviewService", "ICSW_URLS", 'icswSimpleAjaxCall', "blockUI", "$rootScope", "icswUserService",
    "DeviceOverviewSelection",
(
    $scope, icswLayoutSelectionTreeService, $timeout, icswDeviceTreeService, ICSW_SIGNALS,
    icswSelection, icswActiveSelectionService, $q, icswSavedSelectionService, icswToolsSimpleModalService,
    DeviceOverviewService, ICSW_URLS, icswSimpleAjaxCall, blockUI, $rootScope, icswUserService,
    DeviceOverviewSelection
) ->
    # search settings
    $scope.search_ok = true
    $scope.is_loading = true
    $scope.active_tab = "d"
    $scope.show_selection = false
    $scope.saved_selections = []
    $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
    $scope.selection_valid = false
    $scope.synced = false
    # for saved selections
    $scope.vars = {
        "search_str": ""
        "selection_for_dropdown": undefined
    }
    console.log "new ctrl", $scope.$id
    # treeconfig for devices
    $scope.tc_devices = new icswLayoutSelectionTreeService($scope, {show_tree_expand_buttons : false, show_descendants : true})
    # treeconfig for groups
    $scope.tc_groups = new icswLayoutSelectionTreeService($scope, {show_tree_expand_buttons : false, show_descendants : true})
    # treeconfig for categories
    $scope.tc_categories = new icswLayoutSelectionTreeService($scope, {show_selection_buttons : true, show_descendants : true})
    $scope.selection_dict = {
        "d": 0
        "g": 0
        "c": 0
    }
    $scope.tree = undefined
    console.log "start"
    # list of receivers
    stop_listen = []
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_DSR_REGISTERED"), (event) ->
            $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
            console.log "****", $scope.devsel_receivers, $scope
        )
    )
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_USER_CHANGED"), (event, new_user) ->
            console.log "new user", new_user
            if new_user and new_user.idx
                icswDeviceTreeService.fetch($scope.$id).then(
                    (new_tree) ->
                        $scope.got_rest_data(new_tree, icswActiveSelectionService.get_selection())
                )
        )
    )
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_SELECTOR_SHOW"), (event, cur_state) ->
            # call when the requester is shown
            console.log "show_devsel", event, cur_state, $scope
            if icswUserService.user_present()
                icswDeviceTreeService.fetch($scope.$id).then(
                    (new_tree) ->
                        $scope.got_rest_data(new_tree, icswActiveSelectionService.get_selection())
                )
            else
                console.log "No user user"
        )
    )
    stop_listen.push(
        $scope.$on("$destroy", (event) ->
            console.log "Destroy", stop_listen
            (stop_func() for stop_func in stop_listen)
        )
    )
    # get current devsel_receivers
    $scope.got_rest_data = (tree, selection) ->
        $scope.tc_devices.clear_root_nodes()
        $scope.tc_groups.clear_root_nodes()
        $scope.tc_categories.clear_root_nodes()
        $scope.selection = selection
        $scope.selection_valid = true
        console.log "got_rest_data (selection)"
        # build category tree
        # tree category lut
        # id -> category entry from tree (with devices)
        t_cat_lut = {}
        # store tree
        $scope.tree = tree
        console.log tree
        for entry in tree.cat_list
            t_entry = $scope.tc_categories.new_node(
                {
                    folder: true
                    obj: entry.idx
                    _show_select: entry.depth > 1
                    _node_type: "c"
                    expand: entry.depth == 0
                    selected: $scope.selection.category_selected(entry.idx)
                }
            )
            t_cat_lut[entry.idx] = t_entry
            if entry.parent
                t_cat_lut[entry.parent].add_child(t_entry)
            else
                $scope.tc_categories.add_root_node(t_entry)
        # build device group tree and top level of device tree
        dg_lut = {}
        for entry in tree.enabled_list
            if entry.is_meta_device
                g_entry = $scope.tc_groups.new_node(
                    {
                        obj: entry.device_group
                        folder: true
                        _node_type: "g"
                        selected: $scope.selection.device_group_selected(entry.device_group)
                    }
                )
                $scope.tc_groups.add_root_node(g_entry)
                d_entry = $scope.tc_devices.new_node(
                    {
                        obj: entry.idx
                        folder: true
                        _node_type: "d"
                        selected: $scope.selection.device_selected(entry.idx)
                    }
                )
                $scope.tc_devices.add_root_node(d_entry)
                dg_lut[entry.device_group] = d_entry
        # build devices tree
        for entry in tree.enabled_list
            if ! entry.is_meta_device
                # copy selection state to device selection (the selection state of the meta devices is keeped in sync with the selection states of the devicegroups )
                d_entry = $scope.tc_devices.new_node(
                    {
                        obj: entry.idx
                        folder: false
                        _node_type: "d"
                        selected: $scope.selection.device_selected(entry.idx)
                    }
                )
                dg_lut[entry.device_group].add_child(d_entry)
        $scope.tc_devices.prune(
            (entry) ->
                return entry._node_type == "d"
        )
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.recalc()
            cur_tc.show_selected()
        $scope.is_loading = false
        $scope.selection_changed()

    $scope.toggle_show_selection = () ->
        $scope.show_selection = !$scope.show_selection

    $scope.activate_tab = (t_type) ->
        $scope.active_tab = t_type
        for tab_key in ["d", "g", "c"]
            $scope.tabs[tab_key] = tab_key == $scope.active_tab

    $scope.tabs = {}

    $scope.activate_tab($scope.active_tab)

    $scope.get_tc = (short) ->
        return {"d" : $scope.tc_devices, "g": $scope.tc_groups, "c" : $scope.tc_categories}[short]

    $scope.clear_selection = (tab_name) ->
        _tree = $scope.get_tc(tab_name)
        _tree.clear_selected()
        $scope.search_ok = true
        $scope.selection_changed()

    $scope.clear_search = () ->
        if $scope.cur_search_to
            $timeout.cancel($scope.cur_search_to)
        $scope.vars.search_str = ""
        $scope.search_ok = true

    $scope.update_search = () ->
        if $scope.cur_search_to
            $timeout.cancel($scope.cur_search_to)
        $scope.cur_search_to = $timeout($scope.set_search_filter, 500)

    $scope.set_search_filter = () ->
        if $scope.vars.search_str == ""
            return

        looks_like_ip_or_mac_start = (in_str) ->
            # accept "192.168." or "AB:AB:AB:
            return /^\d{1,3}\.\d{1,3}\./.test(in_str) || /^([0-9A-Fa-f]{2}[:-]){3}/.test(in_str)

        if looks_like_ip_or_mac_start($scope.vars.search_str)
            icswSimpleAjaxCall(
                url: ICSW_URLS.DEVICE_GET_MATCHING_DEVICES
                dataType: "json"
                data:
                    search_str: $scope.vars.search_str
            ).then(
                (matching_device_pks) ->
                    cur_tree = $scope.get_tc($scope.active_tab)
                    cur_tree.toggle_tree_state(undefined, -1, false)
                    num_found = 0
                    cur_tree.iter(
                        (entry) ->
                            if entry._node_type == "d"
                                _sel = $scope.tree.all_lut[entry.obj].idx in matching_device_pks
                                entry.set_selected(_sel)
                                if _sel
                                    num_found++
                    )
                    $scope.search_ok = num_found > 0
                    cur_tree.show_selected(false)
                    $scope.selection_changed()
            )

        else  # regular search
            try
                cur_re = new RegExp($scope.vars.search_str, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            cur_tree = $scope.get_tc($scope.active_tab)
            cur_tree.toggle_tree_state(undefined, -1, false)
            num_found = 0
            cur_tree.iter(
                (entry, cur_re) ->
                    if entry._node_type == "d"
                        _sel = if $scope.tree.all_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                    else if entry._node_type == "g"
                        _sel = if $scope.tree.group_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                    else if entry._node_type == "c"
                        _sel = if $scope.tree.cat_lut[entry.obj].name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                cur_re
            )
            $scope.search_ok = if num_found > 0 then true else false
            cur_tree.show_selected(false)
            $scope.selection_changed()

    $scope.resolve_devices = (sel) ->
        return sel.resolve_devices()

    $scope.resolve_total_devices = (sel) ->
        return sel.resolve_total_devices()

    $scope.resolve_device_groups = (sel) ->
        return sel.resolve_device_groups()

    $scope.resolve_categories = (sel) ->
        return sel.resolve_categories()

    $scope.resolve_lazy_selection = () ->
        $scope.selection.resolve_lazy_selection()
        $scope.tc_groups.clear_selected()
        $scope.tc_categories.clear_selected()
        # select devices
        $scope.tc_devices.iter(
            (node, data) ->
                node.selected = node.obj in $scope.selection.tot_dev_sel
        )
        $scope.tc_devices.recalc()
        $scope.tc_groups.show_selected(false)
        $scope.tc_categories.show_selected(false)
        $scope.tc_devices.show_selected(false)
        $scope.selection_changed()
        $scope.activate_tab("d")

    $scope.selection_changed = () ->
        dev_sel_nodes = $scope.tc_devices.get_selected(
            (entry) ->
                if entry._node_type == "d" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        group_sel_nodes = $scope.tc_groups.get_selected(
            (entry) ->
                if entry._node_type == "g" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        cat_sel_nodes = $scope.tc_categories.get_selected(
            (entry) ->
                if entry._node_type == "c" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        $scope.selection_dict = {
            "d": dev_sel_nodes.length
            "g": group_sel_nodes.length
            "c": cat_sel_nodes.length
        }
        # direct selected devices
        dev_sel = []
        # total devices select
        tot_dev_sel = []
        # selected devicegroups (==lazy)
        devg_sel = []
        for _ds in dev_sel_nodes
            dev_sel.push(_ds)
            tot_dev_sel.push(_ds)
        for _gs in group_sel_nodes
            devg_sel.push(_gs)
            for _group_dev in $scope.tree.group_lut[_gs].devices
                tot_dev_sel.push(_group_dev)
        for _cs in cat_sel_nodes
            for _cat_dev in $scope.tree.get_category(_cs).devices
                tot_dev_sel.push(_cat_dev)
        $scope.selection.update(cat_sel_nodes, devg_sel, dev_sel, _.uniq(tot_dev_sel))
        if $scope.selection.is_synced()
            # current selection is in sync with a saved one
            $scope.synced = true
            console.log "sync"
            $scope.selection.compare_with_db()
        else
            console.log "unsync"
            $scope.synced = false

    $scope.call_devsel_func = () ->
        icswActiveSelectionService.send_selection($scope.selection)
        $scope.modal.close()

    $scope.enable_saved_selections = () ->
        if not $scope.saved_selections.length
            icswSavedSelectionService.load_selections().then(
                (data) ->
                    $scope.saved_selections = data
            )

    $scope.update_selection = () ->
        $scope.selection.save_db_obj()
    $scope.create_selection = () ->
        _names = (sel.name for sel in $scope.saved_selections)
        # make name unique
        if $scope.selection.name in _names
            if $scope.selection.name.match(/.* \d+$/)
                _parts = $scope.selection.name.split(" ")
                _idx = parseInt(_parts.pop())
                $scope.selection.name = _parts.join(" ")
            else
                _idx = 1
            while true
                _name = $scope.selection.name + " #{_idx}"
                if _name not in _names
                    break
                else
                    _idx++
            $scope.selection.name = _name
        icswSavedSelectionService.save_selection(
            icswUserService.get(),
            $scope.selection
        ).then(
            (new_sel) ->
                $scope.vars.selection_for_dropdown = $scope.selection.db_obj
                $scope.synced = true
        )
    $scope.unselect = () ->
        console.log "unselect"
        $scope.synced = false
        icswActiveSelectionService.unsync_selection()
        $scope.vars.selection_for_dropdown = undefined
    $scope.use_selection = (new_sel, b) ->
        console.log "use_selection"
        $scope.vars.selection_for_dropdown = new_sel
        icswActiveSelectionService.sync_selection(new_sel)
        (cur_tc.clear_selected() for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories])
        $scope.tc_devices.iter(
            (entry, bla) ->
                if entry._node_type == "d"
                    entry.set_selected($scope.selection.device_selected(entry.obj))
        )
        $scope.tc_groups.iter(
            (entry, bla) ->
                if entry._node_type == "g"
                    entry.set_selected($scope.selection.device_group_selected(entry.obj))
        )
        $scope.tc_categories.iter(
            (entry, bla) ->
                if entry._node_type == "c"
                    entry.set_selected($scope.selection.category_selected(entry.obj))
        )
        # apply new selection
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.recalc()
            cur_tc.show_selected()
        $scope.selection_changed()
    $scope.delete_selection = () ->
        if $scope.synced
            icswToolsSimpleModalService("Delete Selection #{$scope.selection.name} ?").then(
                () ->
                    icswSavedSelectionService.delete_selection($scope.selection).then(
                        (new_list) ->
                            $scope.vars.selection_for_dropdown = undefined
                            $scope.synced = false
                            icswActiveSelectionService.unsync_selection()
                            $scope.saved_selections = new_list
                    )
            )

    $scope.show_current_selection_in_overlay = () ->
        devsel_list = $scope.selection.get_devsel_list()
        selected_devices = ($scope.tree.all_lut[_pk] for _pk in devsel_list[0])
        DeviceOverviewSelection.set_selection(selected_devices)
        DeviceOverviewService(event, selected_devices)
        console.log "show_current_selection"
    $scope.select_parents = () ->
        blockUI.start("Selecting parents...")
        $scope.selection.select_parent().then(
            () ->
                $scope.tc_devices.iter(
                    (node, data) ->
                        node.selected = node.obj in $scope.selection.tot_dev_sel
                )
                $scope.tc_devices.recalc()
                $scope.tc_groups.show_selected(false)
                $scope.tc_categories.show_selected(false)
                $scope.tc_devices.show_selected(false)
                $scope.selection_changed()
                $scope.activate_tab("d")
                blockUI.stop()
        )
]).service("icswLayoutSelectionDialogService", ["$q", "$compile", "$templateCache", "$state", "icswToolsSimpleModalService", "$rootScope", "ICSW_SIGNALS", ($q, $compile, $templateCache, $state, icswToolsSimpleModalService, $rootScope, ICSW_SIGNALS) ->
    # dialog_div =
    prev_left = undefined
    prev_top = undefined
    _active = false
    quick_dialog = () ->
        if !_active
            _active = true
            state_name = $state.current.name
            sel_scope = $rootScope.$new()
            dialog_div = $compile($templateCache.get("icsw.layout.selection.modify"))(sel_scope)
            console.log "SelectionDialog", state_name
            # signal controller
            $rootScope.$emit(ICSW_SIGNALS("ICSW_SELECTOR_SHOW"), state_name)
            BootstrapDialog.show
                message: dialog_div
                title: "Device Selection"
                draggable: true
                animate: false
                closable: true
                onshown: (ref) ->
                    # hack to position to the left
                    _tw = ref.getModal().width()
                    _diag = ref.getModalDialog()
                    if prev_left?
                        $(_diag[0]).css("left", prev_left)
                        $(_diag[0]).css("top", prev_top)
                    else
                        $(_diag[0]).css("left", - (_tw - 600)/2)
                    sel_scope.modal = ref
                onhidden: (ref) ->
                    _diag = ref.getModalDialog()
                    prev_left = $(_diag[0]).css("left")
                    prev_top = $(_diag[0]).css("top")
                    sel_scope.$destroy()
                    _active = false
                buttons: [
                    {
                        icon: "glyphicon glyphicon-ok"
                        cssClass: "btn-warning"
                        label: "close"
                        action: (ref) ->
                            ref.close()
                    }
                ]
    return {
        "quick_dialog": () ->
            return quick_dialog()
    }
]).service("icswLayoutSelectionTreeService", ["DeviceOverviewService", "icswTreeConfig", "icswDeviceTreeService", "DeviceOverviewSelection", (DeviceOverviewService, icswTreeConfig, icswDeviceTreeService, DeviceOverviewSelection) ->
    class selection_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @current = undefined
        ensure_current: () =>
            if not @current
                @current = icswDeviceTreeService.current()
        handle_click: (entry, event) =>
            @ensure_current()
            if entry._node_type == "d"
                dev = @current.all_lut[entry.obj]
                DeviceOverviewSelection.set_selection([dev])
                DeviceOverviewService(event)
                @scope.$apply()
            else
                entry.set_selected(not entry.selected)
                @scope.$digest()
            # need $apply() here, $digest is not enough
        get_name: (t_entry) =>
            @ensure_current()
            entry = @get_dev_entry(t_entry)
            if t_entry._node_type == "f"
                if entry.parent
                    return "#{entry.name} (*.#{entry.full_name})"
                else
                    return "[TLN]"
            else if t_entry._node_type == "c"
                if entry.depth
                    _res = entry.name
                    cat = @current.cat_lut[t_entry.obj]
                    if cat.devices.length
                        _res = "#{_res} (#{cat.devices.length} devices)"
                else
                    _res = "[TOP]"
                return _res
            else if t_entry._node_type == "g"
                _res = entry.name
                group = @current.group_lut[t_entry.obj]
                # ignore meta device
                if group.num_devices
                    _res = "#{_res} (#{group.num_devices} devices)"
                return _res
            else
                info_f = []
                if entry.is_meta_device
                    d_name = entry.full_name.slice(8)
                else
                    d_name = entry.full_name
                if entry.comment
                    info_f.push(entry.comment)
                if info_f.length
                    d_name = "#{d_name} (" + info_f.join(", ") + ")"
                return d_name
        get_icon_class: (t_entry) =>
            if t_entry._node_type == "d"
                entry = @get_dev_entry(t_entry)
                if entry.is_meta_device
                    return "dynatree-icon"
                else
                    return ""
            else
                return "dynatree-icon"
        get_dev_entry: (t_entry) =>
            if t_entry._node_type == "g"
                return @scope.tree.group_lut[t_entry.obj]
            else if t_entry._node_type == "c"
                return @scope.tree.cat_lut[t_entry.obj]
            else
                return @scope.tree.all_lut[t_entry.obj]
        selection_changed: () =>
            @scope.selection_changed()
            console.log "$digest LayoutSel"
            @scope.$digest()
])
