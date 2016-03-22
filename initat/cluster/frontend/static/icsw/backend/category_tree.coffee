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
    "icsw.backend.category_tree",
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
        constructor: (cat_list, ref_list) ->
            @list = []
            @update(cat_list, ref_list)
            @build_luts()

        update: (new_list, ref_list) ->
            # update with new data from server
            REF_NAMES = ["config", "mon_check_command", "deviceselection", "device"]
            @list.length = 0
            for entry in new_list
                if not entry.reference_dict?
                    entry.reference_dict = {}
                for ref_name in REF_NAMES
                    if ref_name not of entry.reference_dict
                        entry.reference_dict[ref_name] = []
                    entry.reference_dict[ref_name].length = 0
                @list.push(entry)
            # intermediat lut
            @lut = _.keyBy(@list, "idx")
            # should be improved, FIXME, TODO
            for ref in ref_list
                @lut[ref[1]].reference_dict[ref[0]].push(ref[2])
            @build_luts()

        build_luts: () =>
            # create lookupTables
            @lut = _.keyBy(@list, "idx")
            @reorder()

        reorder: () =>
            # sort
            @link()

        link: () =>
            # create links
            # clear all child entries
            set_name = (cat, full_name, depth) =>
                cat.full_name = "#{full_name}/#{cat.name}"
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
            for entry in @list
                if entry.depth == 1
                    (set_name(@lut[child], entry.full_name, 1) for child in entry.children)
            @reorder_full_name()

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

]).service("icswCategoryTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswCategoryTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswCategoryTree, $rootScope, ICSW_SIGNALS
) ->
    rest_map = [
        [
            ICSW_URLS.REST_CATEGORY_LIST
            {}
        ]
        [
            ICSW_URLS.BASE_CATEGORY_REFERENCES
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
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** category tree loaded ***"
                if _result?
                    _result.update(data[0], data[1])
                else
                    _result = new icswCategoryTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_CATEGORY_TREE_LOADED"), _result)
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
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
        "reload": (client) ->
            return load_data(client).promise
        "current": () ->
            return _result
    }
])
