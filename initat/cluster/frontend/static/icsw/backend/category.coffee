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
    "icsw.backend.category",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters",
        "ui.select", "restangular",
    ]
).service("icswCategoryTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "$rootScope",
(
    icswTools, ICSW_URLS, $q, Restangular, $rootScope
) ->
    class icswCategoryTree
        constructor: (cat_list, ref_list, gfx_list, dml_list) ->
            @list = []
            @gfx_list = []
            @dml_list = []
            @asset_list = []
            @update(cat_list, ref_list, gfx_list, dml_list)

        update: (new_list, ref_list, gfx_list, dml_list) ->
            # update with new data from server
            @list.length = 0
            for entry in new_list
                @_init_ref_dict(entry, true)
                @list.push(entry)
            # intermediate lut
            @lut = _.keyBy(@list, "idx")
            # link gfx
            @gfx_list.length = 0
            for gfx in gfx_list
                @gfx_list.push(gfx)

            # device monitoring location
            @dml_list.length = 0
            for dml in dml_list
                @dml_list.push(dml)
            # should be improved, FIXME, TODO
            for ref in ref_list
                @lut[ref[1]].reference_dict[ref[0]].push(ref[2])
            # asset list
            @asset_list.length = 0
            for entry in @list
                if entry.asset
                    @asset_list.push(entry)
            @build_luts()

        build_luts: () =>
            # create lookupTables
            @lut = _.keyBy(@list, "idx")
            # gfx lut
            @gfx_lut = _.keyBy(@gfx_list, "idx")
            # dml lut
            @dml_lut = _.keyBy(@dml_list, "idx")
            # asset lut
            @asset_lut = _.keyBy(@asset_list, "idx")
            @reorder()

        reorder: () =>
            # sort
            @link()

        _init_ref_dict: (entry, clear) =>
            REF_NAMES = ["config", "mon_check_command", "deviceselection", "device"]
            if not entry.reference_dict?
                entry.reference_dict = {}
            for ref_name in REF_NAMES
                if ref_name not of entry.reference_dict
                    entry.reference_dict[ref_name] = []
                if clear
                    entry.reference_dict[ref_name].length = 0

        link: () =>
            for entry in @list
                # gfx references, only idx
                if not entry.$gfx_list?
                    entry.$gfx_list = []
                    entry.$dml_list = []
                @_init_ref_dict(entry, false)
            for gfx in @gfx_list
                if not gfx.$dml_list?
                    gfx.$dml_list = []
            # create links
            # clear all child entries
            set_name = (cat, full_name, depth) =>
                cat.full_name = "#{full_name}/#{cat.name}"
                cat.info_string = cat.full_name
                cat.depth = depth + 1
                (set_name(@lut[child], cat.full_name, depth + 1) for child in cat.children)
            # links
            for entry in @list
                entry.children = []
                entry.num_refs = 0
                for key, value of entry.reference_dict
                    entry.num_refs += value.length
            for entry in @list
                if entry.parent
                    @lut[entry.parent].children.push(entry.idx)
                else
                    entry.full_name = entry.name
                    # manually set top-entry info string
                    entry.info_string = "[TOP]"
            for entry in @list
                entry.$gfx_list.length = 0
                entry.$dml_list.length = 0
                if entry.depth == 1
                    entry.info_string = entry.full_name
                    (set_name(@lut[child], entry.full_name, 1) for child in entry.children)
            # gfx list
            for gfx in @gfx_list
                # for speedup
                if gfx.comment
                    gfx.name_comment = "#{gfx.name} (#{gfx.comment})"
                else
                    gfx.name_comment = "#{gfx.name}"
                gfx.info_string = "#{gfx.image_name} #{gfx.width} x #{gfx.height} (#{gfx.content_type})"
                gfx.$dml_list.length = 0
                @lut[gfx.location].$gfx_list.push(gfx)

            # dml
            for dml in @dml_list
                @lut[dml.location].$dml_list.push(dml)
                @gfx_lut[dml.location_gfx].$dml_list.push(dml)

            @reorder_full_name()
            
        # location specific calls
        build_location_list: (loc_list) =>
            loc_list.length = 0
            for entry in @list
                if @is_location(entry, min_depth=2) and entry.useable
                    if not entry.$$expanded?
                        entry.$$expanded = false
                    if not entry.$$selected?
                        entry.$$selected = false
                    if not entry.$gfx_list.length
                        entry.$$expanded = false
                    loc_list.push(entry)

        is_location: (entry, min_depth=0) =>
            return entry.depth >= min_depth and entry.full_name.split("/")[1] == "location"
            
        is_device: (entry, min_depth=0) =>
            return entry.depth >= min_depth and entry.full_name.split("/")[1] == "device"
        
        # resolve categories of device to easier manageable list
        get_device_categories: (dev) =>
            _r_list = []
            for _pk in dev.categories
                _entry = @lut[_pk]
                if @is_device(_entry)
                    _r_list.push(_entry)
            return _r_list        
                
        clear_references: (name) =>
            for entry in @list
                entry.reference_dict[name].length = 0

        sync_devices: (dev_list) =>
            # set device categories from a given device
            for dev in dev_list
                for cat in @list
                    if cat.idx in dev.categories and dev.idx not in cat.reference_dict.device
                        cat.reference_dict.device.push(dev.idx)
                    else if cat.idx not in dev.categories and dev.idx in cat.reference_dict.device
                        _.remove(cat.reference_dict.device, (entry) -> return entry == dev.idx)
            @link()

        feed_config_tree: (ct) =>
            @clear_references("config")
            @clear_references("mon_check_command")
            for config in ct.list
                for cat in config.categories
                    @lut[cat].reference_dict["config"].push(config.idx)
                for mcc in config.mon_check_command_set
                    for cat in mcc.categories
                        @lut[cat].reference_dict["mon_check_command"].push(mcc.idx)
            @link()

        reorder_full_name: () =>
            icswTools.order_in_place(
                @list
                ["full_name"]
                ["asc"]
            )

        # category create / delete functions

        create_category_entry: (new_ce) =>
            # create new category entry
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_CATEGORY_LIST.slice(1)).post(new_ce).then(
                (new_obj) =>
                    @_fetch_category_entry(new_obj.idx, defer, "created category entry")
                (not_ok) ->
                    defer.reject("category entry not created")
            )
            return defer.promise

        delete_category_by_pk: (pk) =>
            _.remove(@list, (entry) -> return entry.idx == pk)
            
        delete_category_entry: (del_ce) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_ce, ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_ce.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == del_ce.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_category_entry: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_CATEGORY_LIST.slice(1)).get({"idx": pk}).then(
                (new_ce) =>
                    new_ce = new_ce[0]
                    @list.push(new_ce)
                    loc_defer = $q.defer()
                    if new_ce.parent and new_ce.parent not of @lut
                        @_fetch_category_entry(new_ce.parent, loc_defer, "intermediate fetch")
                    else
                        loc_defer.resolve("nothing missing")
                    loc_defer.promise.then(
                        (res) =>
                            @build_luts()
                            defer.resolve(msg)
                    )
            )

        # populate all gfx_locations of a given location
        # populate_gfx_location_all: (loc, device_tree, sel_devices) =>
        #    for gfx_loc in loc.$gfx_list
        #        @populate_gfx_location(gfx_loc, device_tree, sel_devices)
                
        # populate gfx_locations
        populate_gfx_location: (gfx_loc, device_tree, sel_devices) =>
            location = @lut[gfx_loc.location]
            # selected device pks
            _sel_pks = (dev.idx for dev in sel_devices)
            # number of devices in map from selection
            gfx_loc.$map_devs_selected = 0
            # number of devices in map, other sources
            gfx_loc.$map_devs_other = 0
            # console.log "sel_pks", _sel_pks
            # local device list
            for entry in gfx_loc.$dml_list
                # restangularize element
                Restangular.restangularizeElement(null, entry, ICSW_URLS.REST_DEVICE_MON_LOCATION_DETAIL.slice(1).slice(0, -2))
                # add $device entries for fast processing in map
                entry.$device = device_tree.all_lut[entry.device]
                entry.$$selected = entry.device in _sel_pks
                if entry.$$selected
                    gfx_loc.$map_devs_selected++
                else
                    gfx_loc.$map_devs_other++
            icswTools.order_in_place(gfx_loc.$dml_list, ["$$selected", "$device.full_name"], ["desc", "asc"])
            gfx_loc.$device_info = (entry.$device.full_name for entry in gfx_loc.$dml_list).join(", ")
            _set_pks = (entry.$device.idx for entry in gfx_loc.$dml_list)
            # _unset_pks = (dev.idx for dev in sel_devices when dev.idx not in _set_pks)
            # list of unset devices
            gfx_loc.$unset_devices = []
            for dev in sel_devices
                if dev.idx not in _set_pks
                    # check if the current location category is valid for the device
                    if gfx_loc.location in dev.categories
                        # physical location in device selection
                        gfx_loc.$unset_devices.push(dev)
            # console.log "g", gfx_loc.idx, gfx_loc.$unset_devices.length
            # console.log gfx_loc.$dml_list
            # console.log gfx_loc.$unset_devices

        # dml create / delete functions

        create_device_mon_location_entry: (new_dml) =>
            # create new category entry
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST.slice(1)).post(new_dml).then(
                (new_obj) =>
                    @_fetch_device_mon_location_entry(new_obj.idx, defer, "created dml entry")
                (not_ok) ->
                    defer.reject("dml entry not created")
            )
            return defer.promise

        _fetch_device_mon_location_entry: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST.slice(1)).get({"idx": pk}).then(
                (new_dml) =>
                    new_dml = new_dml[0]
                    @dml_list.push(new_dml)
                    @build_luts()
                    defer.resolve(msg)
            )

        delete_device_mon_location_entry: (del_dml) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_dml, ICSW_URLS.REST_DEVICE_MON_LOCATION_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_dml.remove().then(
                (ok) =>
                    _.remove(@dml_list, (entry) -> return entry.idx == del_dml.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        # simple remove command for dmls
        remove_dml_by_pk: (del_dml_pk) =>
            _.remove(@dml_list, (entry) -> return entry.idx == del_dml_pk)
            @build_luts()

        # location_gfx create / delete functions

        create_location_gfx_entry: (new_gfx) =>
            # create new category entry
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_LOCATION_GFX_LIST.slice(1)).post(new_gfx).then(
                (new_obj) =>
                    @_fetch_location_gfx_entry(new_obj.idx, defer)
                (not_ok) ->
                    defer.reject("loc_gfx entry not created")
            )
            return defer.promise

        delete_location_gfx_entry: (del_gfx) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_gfx, ICSW_URLS.REST_LOCATION_GFX_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_gfx.remove().then(
                (ok) =>
                    _.remove(@gfx_list, (entry) -> return entry.idx == del_gfx.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        reload_location_gfx_entry: (loc_gfx) =>
            # reload
            defer = $q.defer()
            Restangular.one(ICSW_URLS.REST_LOCATION_GFX_LIST.slice(1)).get({"idx": loc_gfx.idx}).then(
                (new_gfx) =>
                    new_gfx = new_gfx[0]
                    _.remove(@gfx_list, (entry) -> return entry.idx == loc_gfx.idx)
                    @gfx_list.push(new_gfx)
                    @build_luts()
                    defer.resolve("gfx updated")
                (error) =>
                    defer.resolve("Not reloaded")
            )
            return defer.promise
            
        _fetch_location_gfx_entry: (pk, defer) =>
            Restangular.one(ICSW_URLS.REST_LOCATION_GFX_LIST.slice(1)).get({"idx": pk}).then(
                (new_gfx) =>
                    new_gfx = new_gfx[0]
                    @gfx_list.push(new_gfx)
                    @build_luts()
                    defer.resolve(new_gfx)
            )

]).service("icswCategoryTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswTools",
    "icswCategoryTree", "$rootScope", "ICSW_SIGNALS", "icswTreeBase",
(
    $q, Restangular, ICSW_URLS, $window, icswTools,
    icswCategoryTree, $rootScope, ICSW_SIGNALS, icswTreeBase,
) ->
    rest_map = [
        # categories
        ICSW_URLS.REST_CATEGORY_LIST
        # reference counters
        ICSW_URLS.BASE_CATEGORY_REFERENCES
        # location gfx
        ICSW_URLS.REST_LOCATION_GFX_LIST
         # device-location n2m
        ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST
    ]
    return new icswTreeBase(
        "CategoryTree"
        icswCategoryTree
        rest_map
        "ICSW_CATEGORY_TREE_LOADED"
    )

]).service("icswBaseCategoryTree",
[
    "icswTools", "ICSW_URLS", "$q", "Restangular", "$rootScope",
(
    icswTools, ICSW_URLS, $q, Restangular, $rootScope
) ->
    class icswBaseCategoryTree
        constructor: (index_field_name, parent_field_name) ->
            @lut = {}
            @root_nodes = []
            @index_field_name = index_field_name
            @parent_field_name = parent_field_name

        feed: (struct, flag_obj) =>
            _idx = struct[@index_field_name]
            _parent = struct[@parent_field_name]
            _meta_struct = @get_meta_struct(struct, flag_obj)
            @lut[_idx] = _meta_struct
            if  _parent of @lut
                _parent_obj = @lut[_parent]
                @add_to_parent(_parent_obj, _meta_struct)
            else
                @root_nodes.push(_meta_struct)
                _meta_struct.root_node = true
            return _meta_struct

        get_meta_struct: (struct, flag_obj) =>
            return {
                depth: 0
                struct: struct
                childs: []
                # may be a dict or something else
                flags: flag_obj
                root_node: false
                parent: null
            }

        add_to_parent: (parent_struct, meta_struct) =>
            parent_struct.childs.push(meta_struct)
            meta_struct.parent = parent_struct
            meta_struct.depth = parent_struct.depth + 1

        # private function
        _resolve_nodes: (s_node, result_nodes, sel_func) =>
            if sel_func?
                if sel_func(s_node)
                    result_nodes.push(s_node)
            else
                result_nodes.push(s_node)
            (@_resolve_nodes(child, result_nodes, sel_func) for child in s_node.childs)

        get_nodes: () =>
            # return list of nodes which can be added to a TreeStructure, starting with the root nodes
            _nodes = []
            (@_resolve_nodes(_node, _nodes) for _node in @root_nodes)
            return _nodes

        remove_nodes: (remove_func) =>
            # step 1: gather a list of all nodes to be removed
            _to_remove = []
            (@_resolve_nodes(_node, _to_remove, remove_func) for _node in @root_nodes)
            _changed = true
            while _changed
                _changed = false
                _new_to_remove = []
                for entry in _to_remove
                    if not entry.childs.length
                        if entry.parent
                            _.remove(entry.parent.childs, (_entry) -> return _entry.struct.idx == entry.struct.idx)
                        else
                            # root node
                            _.remove(@root_nodes, (_entry) -> return _entry.struct.idx == entry.struct.idx)
                        _changed = true
                        # remove entry
                    else
                        _new_to_remove.push(entry)
                _to_remove = _new_to_remove
])
