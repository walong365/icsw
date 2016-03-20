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

# backend definitions for the domain name tree

angular.module(
    "icsw.backend.domain_name_tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "ui.select", "restangular"
    ]
).service("icswDomainTree",
[
    "icswTools", "Restangular", "$q", "ICSW_URLS",
(
    icswTools, Restangular, $q, ICSW_URLS,
) ->
    class icswDomainTree
        constructor: () ->
            @data_set = false
            @list = []
            @lut = {}

        update: (new_list) =>
            @data_set = true
            @list.length = 0
            for entry in new_list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = icswTools.build_lut(@list)
            # set top level node
            @tln = (entry for entry in @list when entry.depth == 0)[0]
            @reorder()

        reorder: () =>
            # sort
            @link()

        link: () =>
            set_name = (dtn, full_name, sort_name, depth) =>
                if full_name
                    dtn.full_name = "#{dtn.name}.#{full_name}"
                else
                    dtn.full_name = dtn.name
                dtn.tree_info = dtn.full_name
                # $sort_name for correct sorting
                dtn.$sort_name = "#{sort_name}.#{dtn.name}"
                dtn.depth = depth + 1
                (set_name(@lut[child], dtn.full_name, dtn.$sort_name, depth + 1) for child in dtn.$children)
            # create helper entries
            for entry in @list
                entry.$children = []
            for entry in @list
                if entry.parent
                    @lut[entry.parent].$children.push(entry.idx)
                else
                    entry.tree_info = "[TLN]"
                    entry.full_name = entry.name
                    entry.$sort_name = entry.name
            (set_name(@lut[child], @tln.full_name, @tln.$sort_name, 0) for child in @tln.$children)
            @reorder_full_name()

        reorder_full_name: () =>
            icswTools.order_in_place(
                @list
                ["$sort_name"]
                ["asc"]
            )

        # utility functions

        get_full_name: (dev) =>
            if dev.domain_tree_node
                node = @lut[dev.domain_tree_node]
                _name = "#{dev.name}#{node.node_postfix}"
                if node.depth
                    _name = "#{_name}.#{node.full_name}"
                return _name
            else
                return dev.name

        show_dtn: (dev) =>
            if dev.domain_tree_node
                node = @lut[dev.domain_tree_node]
            else
                node = @tln
            r_str = if node.node_postfix then "#{node.node_postfix}" else ""
            if node.depth
                r_str = "#{r_str}.#{node.full_name}"
            else
                r_str = "#{r_str} [TLN]"
            return r_str

        # node creation / deletion service
        create_domain_tree_node_entry: (new_dtn) =>
            # create new domain tree
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST.slice(1)).post(new_dtn).then(
                (new_obj) =>
                    @_fetch_domain_tree_node_entry(new_obj.idx, defer, "created dtn entry")
                (not_ok) ->
                    defer.reject("dtn entry not created")
            )
            return defer.promise

        delete_domain_tree_node_entry: (del_dtn) =>
            # ensure REST hooks
            Restangular.restangularizeElement(null, del_dtn, ICSW_URLS.REST_DOMAIN_TREE_NODE_DETAIL.slice(1).slice(0, -2))
            defer = $q.defer()
            del_dtn.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == del_dtn.idx)
                    @build_luts()
                    defer.resolve("deleted")
                (error) ->
                    defer.reject("not deleted")
            )
            return defer.promise

        _fetch_domain_tree_node_entry: (pk, defer, msg) =>
            Restangular.one(ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST.slice(1)).get({"idx": pk}).then(
                (new_dtn) =>
                    new_dtn = new_dtn[0]
                    @list.push(new_dtn)
                    loc_defer = $q.defer()
                    if new_dtn.parent and new_dtn.parent not of @lut
                        @_fetch_domain_tree_node_entry(new_dtn.parent, loc_defer, "intermediate fetch")
                    else
                        loc_defer.resolve("nothing missing")
                    loc_defer.promise.then(
                        (res) =>
                            @build_luts()
                            defer.resolve(msg)
                    )
            )

]).service('icswDomainTreeService',
[
    "Restangular", "$q", "icswTools", "icswCachingCall", "ICSW_URLS", "icswDomainTree",
(
    Restangular, $q, icswTools, icswCachingCall, ICSW_URLS, icswDomainTree
) ->
    # domain_rest = Restangular.all(ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST.slice(1)).getList().$object
    _fetch_dict = {}
    _result = new icswDomainTree()
    load_called = false
    load_data = (client) ->
        load_called = true
        _wait_list = []
        if client
            _defer = $q.defer()
        icswCachingCall.fetch(client, ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST, [], []).then(
            (data) ->
                _result.update(data)
                if client
                    _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        if client
            return _defer
    trigger_reload = () ->
        # this code works in principle but is not recommended because we will overwrite all local settings
        load_data(null)
    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result.data_set
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]
    return {
        "trigger_reload": () ->
            trigger_reload()
        "load": (client) ->
            # load from server when first load or return result
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
])