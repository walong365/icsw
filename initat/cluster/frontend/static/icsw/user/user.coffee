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
# along with this program; if not, write to the Free Softwareo
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

DT_FORM = "YYYY-MM-DD HH:mm"

class screen_size
    constructor: (@x_size, @y_size) ->
        @idx = @constructor._count++   # must be same as index in list
        @manual = @x_size == 0 and @y_size == 0
        @name = if @manual then "manual" else @x_size+"x"+@y_size
    @_count = 0
    @parse_screen_size: (string) ->
        return string.split "x"

available_screen_sizes = [
    new screen_size(0, 0),
    new screen_size(1920, 1200), new screen_size(1920, 1080),
    new screen_size(1680, 1050), new screen_size(1600, 900),
    new screen_size(1440, 900), new screen_size(1400, 1050),
    new screen_size(1280, 1024), new screen_size(1280, 800),
    new screen_size(1280, 720), new screen_size(1152, 864),
    new screen_size(1024, 768), new screen_size(800, 600),
    new screen_size(640, 420),
]

user_module = angular.module(
    "icsw.user",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "noVNC", "ui.select", "icsw.tools", "icsw.user.password",
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.useraccount", {
            url: "/useraccount"
            templateUrl: "icsw/main/user/account.html"
            data:
                pageTitle: "Account info"
        }
    )
    $stateProvider.state(
        "main.usertree", {
            url: "/usertree"
            templateUrl: "icsw/main/user/tree.html"
            data:
                pageTitle: "User and Group tree"
                menuHeader:
                    key: "sys"
                    name: "System"
                    icon: "fa-cog"
                    ordering: 100
                rights: ["group.group_admin"]
                menuEntry:
                    menukey: "sys"
                    name: "User"
                    icon: "fa-user"
                    ordering: 0
        }
    )
]).service("icswUserGroupTools", [() ->
    return {

        # permission fingerprint
        get_perm_fp: (perm) ->
            if perm.csw_object_permission?
                return "#{perm.level}-#{perm.user}-#{perm.csw_object_permission.csw_permission}-#{perm.csw_object_permission.object_pk}"
            else
                return "#{perm.level}-#{perm.user}-#{perm.csw_permission}"

        # check if changed
        changed: (object) ->
            return object.$$_ICSW_backup_def.changed(object)

    }
]).service("icswUserService",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "$rootScope",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, $rootScope
) ->
    _last_load = 0
    current_user = undefined
    set_user = (user) ->
        current_user = user
        $rootScope.$emit("icsw.user.changed", current_user)
    set_user(undefined)
    _fetch_pending = false
    _force_logout = false
    load_user = (cache) ->
        cur_time = moment().unix()
        _diff_time = Math.abs(cur_time - _last_load)
        _defer = $q.defer()
        if _diff_time > 5 or not cache
            _fetch_pending = true
            icswSimpleAjaxCall(
                url: ICSW_URLS.SESSION_GET_AUTHENTICATED_USER,
                dataType: "json"
            ).then(
                (data) ->
                    _fetch_pending = false
                    if _force_logout
                        _force_logout = false
                        logout_user()
                    else
                        _last_load = moment().unix()
                        set_user(data)
                    _defer.resolve(current_user)
                (error) ->
                    _fetch_pending = false
            )
        else
            _defer.resolve(current_user)
        return _defer
    force_logout = () ->
        if _fetch_pending
            _force_logout = true
    logout_user = () ->
        _defer = $q.defer()
        set_user(undefined)
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.SESSION_LOGOUT
                dataType: "json"
            }
        ).then(
            (json) ->
                _defer.resolve(json)
        )
        return _defer
    return {
        "load": (cache) ->
            # loads from server
            return load_user(cache).promise
        "logout": () ->
            return logout_user().promise
        "get": () ->
            return current_user
        "user_present": () ->
            return if current_user then true else false
        "force_logout": () ->
            # force user logout, also when a (valid) load_user request is pending
            force_logout()
    }
]).service("icswUserGroupPermissionTree",
[
    "$q",
(
    $q,
) ->
    # permission list and objects
    class icswUserGroupPermissionTree
        constructor: (permission_list, object_level_list) ->
            @permission_list = []
            # special object list
            @object_level_list = []
            @ac_level_list = [
                {"level": 0, "info_string": "Read-only"},
                {"level": 1, "info_string": "Modify"},
                {"level": 3, "info_string": "Modify, Create"},
                {"level": 7, "info_string": "Modify, Create, Delete"},
            ]
            @update(permission_list, object_level_list)
        
        update: (perm_list, obj_level_list) =>
            @permission_list.length = 0
            for entry in perm_list
                @permission_list.push(entry)
                key = entry.content_type.app_label + "." + entry.content_type.model
                entry.key = key
            @object_level_list.length = 0
            for entry in obj_level_list
                @object_level_list.push(entry)
            @build_luts()
        
        build_luts: () =>
            @permission_lut = _.keyBy(@permission_list, "idx")
            @object_level_lut_by_type = _.keyBy(@object_level_list, "content_type")
            @object_level_lut_by_label = _.keyBy(@object_level_list, "content_label")
            # model permissions, key is app_label.content_type
            @model_permission_lut = {}
            for entry in @permission_list
                if entry.valid_for_object_level
                    if entry.key not of @model_permission_lut
                        @model_permission_lut[entry.key] = []
                    @model_permission_lut[entry.key].push(entry)
            @ac_level_lut = _.keyBy(@ac_level_list, "level")
            @link()

        link: () =>
            # create info fields
            for entry in @permission_list
                entry.model_name = entry.content_type.model
                if entry.valid_for_object_level
                    info_str = "#{entry.name} (G/O)"
                else
                    info_str = "#{entry.name} (G)"
                entry.info_string = info_str

]).service("icswUserGroupPermissionTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswUserGroupPermissionTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswUserGroupPermissionTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_CSW_PERMISSION_LIST, {}
        ]
        [
            ICSW_URLS.REST_CSW_OBJECT_LIST, {}
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
                console.log "*** user/group permission tree loaded ***"
                _result = new icswUserGroupPermissionTree(data[0], data[1])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
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
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).service("icswUserGroupSettingsTree",
[
    "$q",
(
    $q,
) ->
    # various settings for users and group
    class icswUserGroupSettingsTree
        constructor: (
            home_export_list,
            quota_capable_blockdevice_list,
            virtual_desktop_protocol_list,
            window_manager_list,
        ) ->
            @home_export_list = []
            @quota_capable_blockdevice_list = []
            @virtual_desktop_protocol_list = []
            @window_manager_list = []
            @update(home_export_list, quota_capable_blockdevice_list, virtual_desktop_protocol_list, window_manager_list)

        update: (he_list, qcb_list, vdp_list, wm_list) =>
            @home_export_list.length = 0
            for entry in he_list
                @home_export_list.push(entry)
            @quota_capable_blockdevice_list.length = 0
            for entry in qcb_list
                @quota_capable_blockdevice_list.push(entry)
            @virtual_desktop_protocol_list.length = 0
            for entry in vdp_list
                @virtual_desktop_protocol_list.push(entry)
            @window_manager_list.length = 0
            for entry in wm_list
                @window_manager_list.push(entry)
            @build_luts()

        build_luts: () =>
            @home_export_lut = _.keyBy(@home_export_list, "idx")
            @quota_capable_blockdevice_lut = _.keyBy(@quota_capable_blockdevice_list, "idx")
            @virtual_desktop_protocol_lut = _.keyBy(@virtual_desktop_protocol_list, "idx")
            @window_manager_lut = _.keyBy(@window_manager_list, "idx")

]).service("icswUserGroupSettingsTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswUserGroupSettingsTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswUserGroupSettingsTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_HOME_EXPORT_LIST, {}
        ]
        [
            ICSW_URLS.REST_QUOTA_CAPABLE_BLOCKDEVICE_LIST, {}
        ]
        [
            ICSW_URLS.REST_VIRTUAL_DESKTOP_PROTOCOL_LIST, {}
        ]
        [
            ICSW_URLS.REST_WINDOW_MANAGER_LIST, {}
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
                console.log "*** user/group settings tree loaded ***"
                _result = new icswUserGroupSettingsTree(data[0], data[1], data[2], data[3])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
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
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).service("icswUserGroupTree",
[
    "$q",
(
    $q
) ->
    # user / group tree representation
    class icswUserGrouptree
        constructor: (user_list, group_list, vdus_list) ->
            @user_list =[]
            @group_list = []
            @vdus_list = []
            @update(user_list, group_list, vdus_list)

        update: (user_list, group_list, vdus_list) =>
            @user_list.length = 0
            @group_list.length = 0
            for user in user_list
                if not user.vdus_list?
                    user.vdus_list = []
                user.vdus_list.length = 0
                @user_list.push(user)
            for group in group_list
                @group_list.push(group)
            @vdus_list.length = 0
            for entry in vdus_list
                @vdus_list.push(entry)
            @build_luts()

        build_luts: () =>
            @user_lut = _.keyBy(@user_list, "idx")
            @group_lut = _.keyBy(@group_list, "idx")
            @vdus_lut = _.keyBy(@vdus_list, "idx")
            @link()

        link: () =>
            # create usefull links
            for vdus in @vdus_list
                @user_lut[vdus.user].vdus_list.push(vdus)

]).service("icswUserGroupTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswUserGroupTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswUserGroupTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_USER_LIST, {}
        ]
        [
            ICSW_URLS.REST_GROUP_LIST, {}
        ]
        [
            ICSW_URLS.REST_VIRTUAL_DESKTOP_USER_SETTING_LIST, {}
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
                console.log "*** user/group tree loaded ***"
                _result = new icswUserGroupTree(data[0], data[1], data[2])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_LOADED"), _result)
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
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).service("icswUserGroupDisplayTree",
[
    "icswTreeConfig",
(
    icswTreeConfig
) ->
    class icswUserGroupDisplayTree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = true
            @show_select = false
            @show_descendants = true
            @show_childs = false
            @init_feed()

        init_feed: () =>
            @user_lut = {}
            @group_lut = {}

        get_name : (t_entry) ->
            ug = t_entry.obj
            if t_entry._node_type == "g"
                _name = ug.groupname
                _if = ["gid #{ug.gid}"]
            else
                _name = ug.login
                _if = ["uid #{ug.uid}"]
            if ! ug.active
                _if.push("inactive")
            return "#{_name} (" + _if.join(", ") + ")"

        add_extra_span: (entry) ->
            return angular.element("<span><span/><span/><span style='width:8px;'>&nbsp;</span></span>")

        update_extra_span: (entry, div) ->
            if entry._node_type == "u"
                span = div.find("span:nth-child(1)")
                span.removeClass()
                if entry.obj.only_webfrontend
                    span.addClass("fa fa-genderless fa-fw")

        handle_click: (entry, event) =>
            @clear_active()
            entry.active = true
            @scope.add_edit_object_from_tree(entry)
            @scope.$digest()

        get_icon_class: (entry) ->
            if entry._node_type == "u"
                if entry.obj.is_superuser
                    return "fa fa-user-plus"
                else
                    return "fa fa-user"
            else
                return "fa fa-group"

]).service("icswDiskUsageTree", ["icswTreeConfig", (icswTreeConfig) ->
    class icsw_disk_usage_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = true
            @show_select = false
            @show_descendants = true
            @show_childs = false
        get_name : (t_entry) ->
            _dir = t_entry.obj
            _size_total = _dir.size_total
            _size = _dir.size
            _size_total_str = @scope.icswTools.get_size_str(_size_total, 1024, "B")
            if _size_total == _size
                _info = ["#{_size_total_str} total"]
            else
                if _size
                    _size_str = @scope.icswTools.get_size_str(_size, 1024, "B")
                    _info = [
                        "#{_size_total_str} total",
                        "#{_size_str} in directory"
                    ]
                else
                    _info = ["#{_size_total_str} total"]
            if _dir.num_files_total
                _info.push(@scope.icswTools.get_size_str(_dir.num_files_total, 1000, "") + " files")
            return "#{_dir.name} (" + _info.join(", ") + ")"
]).controller("icswUserGroupTreeCtrl", [
    "icswUserGroupTreeService", "$scope", "$compile", "$q", "icswUserGroupSettingsTreeService", "blockUI",
    "icswUserGroupPermissionTreeService", "icswUserGroupDisplayTree", "$timeout", "icswDeviceTreeService",
    "icswUserBackup", "icswGroupBackup", "icswUserGroupTools", "ICSW_SIGNALS", "icswToolsSimpleModalService",
    "icswSimpleAjaxCall", "ICSW_URLS",
(
    icswUserGroupTreeService, $scope, $compile, $q, icswUserGroupSettingsTreeService, blockUI,
    icswUserGroupPermissionTreeService, icswUserGroupDisplayTree, $timeout, icswDeviceTreeService,
    icswUserBackup, icswGroupBackup, icswUserGroupTools, ICSW_SIGNALS, icswToolsSimpleModalService,
    icswSimpleAjaxCall, ICSW_URLS,
) ->
    $scope.struct = {
        # any tree data valid
        tree_loaded: false
        # user and group tree
        user_group_tree: undefined
        # user and group settings
        ugs_tree: undefined
        # user and group permission tree
        perm_tree: undefined
        # error string (info string
        error_string: ""
        # display tree
        display_tree: new icswUserGroupDisplayTree($scope)
        # filter string
        filterstr: ""
        # edit groups and users
        edit_groups: []
        edit_users: []
    }

    $scope.reload = () ->
        $scope.struct.error_string = "loading tree..."
        $scope.struct.edit_groups.length = 0
        $scope.struct.edit_users.length = 0
        $q.all(
            [
                icswUserGroupTreeService.load($scope.$id)
                icswUserGroupSettingsTreeService.load($scope.$id)
                icswUserGroupPermissionTreeService.load($scope.$id)
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.user_group_tree = data[0]
                $scope.struct.ugs_tree = data[1]
                $scope.struct.perm_tree = data[2]
                $scope.struct.device_tree = data[3]
                $scope.struct.error_string = ""
                $scope.rebuild_tree()
                $scope.struct.tree_loaded = true
        )

        $scope.rebuild_tree = () ->
            _get_parent_group_list = (cur_group) ->
                _list = []
                for _group in _ugt.group_list
                    if _group.idx != cur_group.idx
                        add = true
                        # check if cur_group is not a parent
                        _cur_p = _group.parent_group
                        while _cur_p
                            _cur_p = _ugt.group_lut[_cur_p]
                            if _cur_p.idx == cur_group.idx
                                add = false
                            _cur_p = _cur_p.parent_group
                        if add
                            _list.push(_group)
                return _list

            _ugt = $scope.struct.user_group_tree
            _dt = $scope.struct.display_tree
            # init tree
            _dt.clear_root_nodes()
            _dt.init_feed()
            # groups to add later
            rest_list = []
            # add groups
            for entry in _ugt.group_list
                # set csw dummy permission list and optimizse object_permission list
                # $scope.init_csw_cache(entry, "group")
                t_entry = _dt.new_node(
                    folder: true
                    obj: entry
                    expand: !entry.parent_group
                    _node_type: "g"
                    always_folder: true
                )
                _dt.group_lut[entry.idx] = t_entry
                if entry.parent_group
                    # handle later
                    rest_list.push(t_entry)
                else
                    _dt.add_root_node(t_entry)
            while rest_list.length > 0
                # iterate until the list is empty
                _rest_list = []
                for entry in rest_list
                    if entry.obj.parent_group of _dt.group_lut
                        _dt.group_lut[entry.obj.parent_group].add_child(entry)
                    else
                        _rest_list.push(entry)
                rest_list = _rest_list
            # parent group dict
            _pgs = {}
            for entry in _ugt.group_list
                _pgs[entry.idx] = _get_parent_group_list(entry)
            $scope.parent_groups = _pgs
            # console.log "*", $scope.parent_groups
            # add users
            for entry in _ugt.user_list
                # set csw dummy permission list and optimise object_permission_list
                # $scope.init_csw_cache(entry, "user")
                t_entry = _dt.new_node(
                    {
                        folder: false
                        obj: entry
                        _node_type: "u"
                    }
                )
                _dt.group_lut[entry.group].add_child(t_entry)

    # filter functions

    $scope.update_filter = () ->
        _filter_to = () ->
            if not $scope.struct.filterstr
                cur_re = new RegExp("^$", "gi")
            else
                try
                    cur_re = new RegExp($scope.struct.filterstr, "gi")
                catch exc
                    cur_re = new RegExp("^$", "gi")
            _dt = $scope.struct.display_tree
            _dt.iter(
                (entry, cur_re) ->
                    cmp_name = if entry._node_type == "g" then entry.obj.groupname else entry.obj.login
                    entry.active = if cmp_name.match(cur_re) then true else false
                cur_re
            )
            _dt.show_active(false)

        if $scope.update_filter_to?
            $timeout.cancel($scope.update_filter_to)
        $scope.update_filter_to = $timeout(_filter_to, 200)

    # edit object functions

    $scope.add_edit_object_from_tree = (treenode) ->
        if treenode._node_type == "g"
            $scope.add_edit_object(treenode.obj, "group")
        else
            $scope.add_edit_object(treenode.obj, "user")

    $scope.add_edit_object = (obj, obj_type) ->
        if obj_type == "group"
            ref_list = $scope.struct.edit_groups
            bu_def = icswGroupBackup
        else
            ref_list = $scope.struct.edit_users
            bu_def = icswUserBackup
        if obj not in ref_list
            bu_obj = new bu_def()
            bu_obj.create_backup(obj)
            # console.log bu_obj, obj
            ref_list.push(obj)

    # close open tabs

    close_edit_object = (ref_obj, ref_list, obj_type) ->
        defer = $q.defer()
        # must use a timeout here to fix strange routing bug, FIXME, TODO
        if icswUserGroupTools.changed(ref_obj)
            icswToolsSimpleModalService("Really close changed #{obj_type} ?").then(
                (ok) ->
                    defer.resolve("close")
                (not_ok) ->
                    defer.reject("not closed")
            )
        else
            defer.resolve("not changed")
        defer.promise.then(
            (close) ->
                $timeout(
                    () ->
                        _.remove(ref_list, (entry) -> return ref_obj.idx == entry.idx)
                    100
                )
        )

    $scope.$on(ICSW_SIGNALS("_ICSW_CLOSE_USER_GROUP"), ($event, object, obj_type) ->
        if obj_type == "group"
            $scope.close_group(object)
        else
            $scope.close_user(object)
    )

    $scope.close_group = (group_obj) ->
        close_edit_object(group_obj, $scope.struct.edit_groups, "group")

    $scope.close_user = (user_obj) ->
        close_edit_object(user_obj, $scope.struct.edit_users, "user")

    $scope.changed = (object) ->
        return icswUserGroupTools.changed(object)

    $scope.create_group = () ->
        gid = 200
        gids = (entry.gid for entry in $scope.struct.user_group_tree.group_list)
        for entry in $scope.struct.edit_groups
            gids.push(entry.gid)
        while gid in gids
            gid++
        new_group = {
            groupname: "new_group"
            gid: gid
            active: true
            homestart: "/home"
            group_quota_setting_set: []
            group_permission_set: []
            group_object_permission_set: []
        }
        $scope.add_edit_object(new_group, "group")

    $scope.create_user = () ->
        uid = 200
        uids = (entry.uid for entry in $scope.struct.user_group_tree.user_list)
        for entry in $scope.struct.edit_users
            uids.push(entry.uid)
        while uid in uids
            uid++
        new_user = {
            login: "new_user"
            uid: uid
            active: true
            db_is_auth_for_password: true
            password: ""
            group: $scope.struct.user_group_tree.group_list[0].idx
            shell: "/bin/bash"
            scan_depth: 2
            secondary_groups: []
            user_quota_setting_set: []
            user_permission_set: []
            user_object_permission_set: []
        }
        $scope.add_edit_object(new_user, "user")

    $scope.sync_users = () ->
        blockUI.start("Sending sync to server ...")
        icswSimpleAjaxCall(
            url: ICSW_URLS.USER_SYNC_USERS
            title: "syncing users"
        ).then(
            (xml) ->
                blockUI.stop()
            (xml) ->
                blockUI.stop()
        )

    $scope.reload()
]).controller("user_tree", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$timeout", "$uibModal", "blockUI", "ICSW_URLS", "icswSimpleAjaxCall", "toaster", "icswAcessLevelService",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $timeout, $uibModal, blockUI, ICSW_URLS, icswSimpleAjaxCall, toaster, icswAcessLevelService) ->
        $scope.valid_group_csw_perms = () ->
            _list = (entry for entry in $scope.csw_permission_list when entry.codename not in ["admin", "group_admin"])
            return _list
        $scope.valid_user_csw_perms = () ->
            return (entry for entry in $scope.csw_permission_list)

        $scope.get_export_list = () ->
            for entry in $scope.home_export_list
                entry.home_info_string = $scope.get_home_info_string(entry)
            return $scope.home_export_list
        $scope.get_home_info_string = (entry) ->
            cur_group = (_entry for _entry in $scope.group_list when _entry.idx == $scope._edit_obj.group)
            if cur_group.length
                cur_group = cur_group[0]
            else
                cur_group = null
            if entry.createdir
                info_string = "#{entry.homeexport} (created in #{entry.createdir}) on #{entry.full_name}"
            else
                info_string = "#{entry.homeexport} on #{entry.full_name}"
            if cur_group
                info_string = "#{info_string}, #{cur_group.homestart}/#{$scope._edit_obj.login}"
            return info_string
        $scope.create_group = () ->
            $scope._edit_mode = "g"
            $scope.group_edit.create()
        $scope.create_user = () ->
            $scope._edit_mode = "u"
            $scope.user_edit.create()
        $scope.edit_object = (obj, obj_type) ->
            # init dummy form object for subscope(s)
            $scope._edit_mode = obj_type
            if obj_type == "g"
                $scope.group_edit.edit(obj)
            else if obj_type == "u"
                $scope.user_edit.edit(obj)
        $scope.$on("icsw.set_password", (event, new_pwd) ->
            $scope._edit_obj.password = new_pwd
            if $scope._edit_obj.idx?
                $scope._edit_obj.put()
            $scope.$digest()
        )
        $scope.create_object_permission = () ->
            perm = $scope.csw_permission_lut[$scope._edit_obj.permission]
            icswSimpleAjaxCall(
                url     : ICSW_URLS.USER_CHANGE_OBJECT_PERMISSION
                data    :
                    # group or user
                    "auth_type": $scope._edit_mode
                    "auth_pk": $scope._edit_obj.idx
                    "model_label": perm.content_type.model
                    "obj_idx": $scope._edit_obj.object
                    "csw_idx": $scope._edit_obj.permission
                    "set": 1
                    "level": $scope._edit_obj.permission_level
            ).then((xml) ->
                if $(xml).find("value[name='new_obj']").length
                    new_obj = angular.fromJson($(xml).find("value[name='new_obj']").text())
                    if $scope._edit_mode == "u"
                        $scope._edit_obj.user_object_permission_set.push(new_obj)
                    else
                        $scope._edit_obj.group_object_permission_set.push(new_obj)
                    toaster.pop("success", "", "added local permission")
            )
        $scope.delete_permission = (perm) ->
            if $scope._edit_mode == "u"
                ug_name = "user"
                detail_url = ICSW_URLS.REST_USER_PERMISSION_DETAIL.slice(1).slice(0, -2)
            else
                ug_name = "group"
                detail_url = ICSW_URLS.REST_GROUP_PERMISSION_DETAIL.slice(1).slice(0, -2)
            ps_name = "#{ug_name}_permission_set"
            Restangular.restangularizeElement(null, perm, detail_url)
            perm.remove().then((data) ->
                $scope._edit_obj[ps_name] = (_e for _e in $scope._edit_obj[ps_name] when _e.csw_permission != perm.csw_permission)
                toaster.pop("warning", "", "removed global #{ug_name} permission")
            )
        $scope.delete_object_permission = (perm) ->
            if $scope._edit_mode == "u"
                ug_name = "user"
                detail_url = ICSW_URLS.REST_USER_OBJECT_PERMISSION_DETAIL.slice(1).slice(0, -2)
            else
                ug_name = "group"
                detail_url = ICSW_URLS.REST_GROUP_OBJECT_PERMISSION_DETAIL.slice(1).slice(0, -2)
            ps_name = "#{ug_name}_object_permission_set"
            Restangular.restangularizeElement(null, perm, detail_url)
            perm.remove().then((data) ->
                $scope._edit_obj[ps_name] = (_e for _e in $scope._edit_obj[ps_name] when _e.idx != perm.idx)
                toaster.pop("warning", "", "removed local #{ug_name} permission")
            )
        $scope.create_permission = () ->
            if $scope._edit_obj.permission
                if $scope._edit_mode == "u"
                    ug_name = "user"
                    list_url = ICSW_URLS.REST_USER_PERMISSION_LIST.slice(1)
                else
                    ug_name = "group"
                    list_url = ICSW_URLS.REST_GROUP_PERMISSION_LIST.slice(1)
                ps_name = "#{ug_name}_permission_set"
                if not (true for _e in $scope._edit_obj[ps_name] when _e.csw_permission == $scope._edit_obj.permission).length
                    new_obj = {
                        "csw_permission" : $scope._edit_obj.permission
                        "level" : $scope._edit_obj.permission_level
                    }
                    $scope._edit_obj.permission = null
                    new_obj[ug_name] = $scope._edit_obj.idx
                    Restangular.all(list_url).post(new_obj).then(
                        (data) ->
                            $scope._edit_obj[ps_name].push(data)
                    )
        $scope.get_perm_level = (perm) ->
            level = perm.level
            return (_v.info for _v in $scope.ac_levels when _v.level == level)[0]
        $scope.get_perm_model = (perm) ->
            return $scope.csw_permission_lut[perm.csw_permission].content_type.model
        $scope.get_perm_type = (perm) ->
            return if $scope.csw_permission_lut[perm.csw_permission].valid_for_object_level then "G / O" else "G"
        $scope.get_home_dir_created_class = (obj) ->
            if obj.home_dir_created
                return "btn btn-sm btn-success"
            else
                return "btn btn-sm btn-danger"
        $scope.get_home_dir_created_value = (obj) ->
            return if obj.home_dir_created then "homedir exists" else "no homedir"
        $scope.clear_home_dir_created = (obj) ->
            icswSimpleAjaxCall(
                url     : ICSW_URLS.USER_CLEAR_HOME_DIR_CREATED
                data    :
                    "user_pk" : obj.idx
            ).then((xml) ->
                obj.home_dir_created = false
            )
        $scope.get_perm_object = (perm) ->
            obj_perm = perm.csw_object_permission
            csw_perm = $scope.csw_permission_lut[obj_perm.csw_permission]
            key = "#{csw_perm.content_type.app_label}.#{csw_perm.content_type.model}"
            return (_v.name for _v in $scope.ct_dict[key] when _v.idx == obj_perm.object_pk)[0]

        $scope.push_virtual_desktop_user_setting = (new_obj, then_fun) ->
            url = ICSW_URLS.REST_VIRTUAL_DESKTOP_USER_SETTING_LIST.slice(1)
            Restangular.all(url).post(new_obj).then( then_fun )
        $scope.get_viewer_command_line = (vdus) ->
            icswSimpleAjaxCall(
                url      : ICSW_URLS.USER_GET_DEVICE_IP
                data     :
                    "device" : vdus.device
                dataType : "json"
            ).then((json) ->
                vdus.viewer_cmd_line = virtual_desktop_utils.get_viewer_command_line(vdus, json.ip)
                script = "notepad.exe\r\n"
                blob = new Blob([ script ], { type : 'application/x-bat' });
                # console.log "blob", blob
                vdus.testurl = (window.URL || window.webkitURL).createObjectURL( blob );
            )
]).controller("icswUserAccountCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$timeout", "$uibModal", "ICSW_URLS", "icswUserService",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $timeout, $uibModal, ICSW_URLS, icswUserService) ->
        $scope.virtual_desktop_user_setting = []
        $scope.ac_levels = [
            {"level" : 0, "info" : "Read-only"},
            {"level" : 1, "info" : "Modify"},
            {"level" : 3, "info" : "Modify, Create"},
            {"level" : 7, "info" : "Modify, Create, Delete"},
        ]
        $scope.update = () ->
            icswUserService.load().then((user) ->
                wait_list = restDataSource.add_sources([
                    [ICSW_URLS.REST_CSW_PERMISSION_LIST, {}]
                    [ICSW_URLS.REST_CSW_OBJECT_LIST, {}]
                    [ICSW_URLS.REST_QUOTA_CAPABLE_BLOCKDEVICE_LIST, {}]
                    [ICSW_URLS.REST_VIRTUAL_DESKTOP_USER_SETTING_LIST, {}]
                    [ICSW_URLS.REST_VIRTUAL_DESKTOP_PROTOCOL_LIST, {}]
                    [ICSW_URLS.REST_WINDOW_MANAGER_LIST, {}]
                    [ICSW_URLS.REST_DEVICE_LIST, {}]
                ])
                wait_list.push(Restangular.one(ICSW_URLS.REST_USER_DETAIL.slice(1).slice(0, -2), user.idx).get())
                $q.all(wait_list).then(
                    (data) ->
                        # update once per minute
                        $timeout($scope.update, 60000)
                        $scope.edit_obj = data[7]
                        $scope.csw_permission_list = data[0]
                        $scope.csw_permission_lut = {}
                        for entry in $scope.csw_permission_list
                            $scope.csw_permission_lut[entry.idx] = entry
                        $scope.ct_dict = {}
                        for entry in data[1]
                            $scope.ct_dict[entry.content_label] = entry.object_list
                        $scope.qcb_list = data[2]
                        $scope.qcb_lut = {}
                        for entry in $scope.qcb_list
                            $scope.qcb_lut[entry.idx] = entry
                        $scope.virtual_desktop_user_setting = data[3]
                        $scope.virtual_desktop_protocol = data[4]
                        $scope.window_manager = data[5]
                        $scope.device = data[6]
                )
            )
        $scope.update_account = () ->
            $scope.edit_obj.put().then(
               (data) ->
               (resp) ->
            )
        $scope.$on("icsw.set_password", (event, new_pwd) ->
            $scope.edit_obj.password = new_pwd
            $scope.update_account()
            $scope.$digest()
        )
        $scope.get_perm_app = (perm) ->
            return $scope.csw_permission_lut[perm.csw_permission].content_type.app_label
        $scope.get_obj_perm_app = (perm) ->
            return $scope.csw_permission_lut[perm.csw_permission].content_type.app_label
        $scope.get_perm_level = (perm) ->
            level = perm.level
            return (_v.info for _v in $scope.ac_levels when _v.level == level)[0]
        $scope.get_perm_model = (perm) ->
            return $scope.csw_permission_lut[perm.csw_permission].content_type.model
        $scope.get_perm_type = (perm) ->
            return if $scope.csw_permission_lut[perm.csw_permission].valid_for_object_level then "G / O" else "G"
        $scope.get_perm_object = (perm) ->
            obj_perm = perm.csw_object_permission
            csw_perm = $scope.csw_permission_lut[obj_perm.csw_permission]
            key = "#{csw_perm.content_type.app_label}.#{csw_perm.content_type.model}"
            return (_v.name for _v in $scope.ct_dict[key] when _v.idx == obj_perm.object_pk)[0]
        $scope.get_vdus = (idx) ->
        $scope.update()
]).directive("icswUserEdit",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.user.edit.form")
        controller: "icswUserGroupEditCtrl"
        scope:
            user: "=icswUser"
            tree: "=icswUserGroupTree"
            perm_tree: "=icswPermissionTree"
            device_tree: "=icswDeviceTree"
            settings_tree: "=icswUserGroupSettingsTree"
        link: (scope, element, attrs) ->
            scope.set_type("user")
    }
]).directive("icswGroupEdit",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.group.edit.form")
        controller: "icswUserGroupEditCtrl"
        scope:
            group: "=icswGroup"
            tree: "=icswUserGroupTree"
            perm_tree: "=icswPermissionTree"
            device_tree: "=icswDeviceTree"
            settings_tree: "=icswUserGroupSettingsTree"
        link: (scope, element, attrs) ->
            scope.set_type("group")
    }
]).controller("icswUserGroupEditCtrl",
[
    "$scope", "$q", "icswUserGroupTools", "ICSW_SIGNALS", "icswToolsSimpleModalService", "icswUserGetPassword",
(
    $scope, $q, icswUserGroupTools, ICSW_SIGNALS, icswToolsSimpleModalService, icswUserGetPassword,
) ->

    $scope.obj_list_cache = {}
    $scope.obj_lut_cache = {}

    $scope.new_perm = {
        permission: undefined
        level: 0
        object: undefined
    }

    $scope.set_type = (ug_type) ->
        $scope.type = ug_type
        if $scope.type == "user"
            # original
            $scope.src_object = $scope.user
            # working object
            $scope.object = $scope.src_object.$$_ICSW_backup_data
            $scope.permission_set = $scope.object.user_permission_set
            $scope.object_permission_set = $scope.object.user_object_permission_set
            # check password
            if $scope.user.password.length
                $scope.modify_ok = true
            else
                $scope.modify_ok = false
        else
            # original
            $scope.src_object = $scope.group
            # working object
            $scope.object = $scope.src_object.$$_ICSW_backup_data
            $scope.permission_set = $scope.object.group_permission_set
            $scope.object_permission_set = $scope.object.group_object_permission_set

    _object_list = (key) ->
        if key not of $scope.obj_list_cache
            _list = []
            if key == "backbone.device"
                for entry in $scope.device_tree.enabled_list
                    if entry.is_meta_device
                        if entry.is_cluster_device_group
                            _name = "[CDG] " + entry.full_name.substr(8)
                        else
                            _name = "[MD] " + entry.full_name.substr(8)
                    else
                        _name = entry.full_name
                    _list.push(
                        {
                            idx: entry.idx
                            name: _name
                            group: "DeviceGroup " + $scope.device_tree.group_lut[entry.device_group].name
                        }
                    )
            else if key == "backbone.user"
                for entry in $scope.tree.user_list
                    _list.push(
                        {
                            idx: entry.idx
                            name: entry.login
                            group: "Group " + $scope.tree.group_lut[entry.group].groupname
                        }
                    )
            else if key == "backbone.group"
                for entry in $scope.tree.group_list
                    _list.push(
                        {
                            idx: entry.idx
                            name: entry.groupname
                            group: ""
                        }
                    )
            else
                console.error "unknown OLP-key '#{key}'"
            $scope.obj_list_cache[key] = _list
            $scope.obj_lut_cache[key] = _.keyBy(_list, "idx")
        return $scope.obj_list_cache[key]

    $scope.get_perm = (perm) ->
        return $scope.perm_tree.permission_lut[perm]

    $scope.object_list = () ->
        if $scope.new_perm.permission
            _list = []
            # create cache
            perm = $scope.perm_tree.permission_lut[$scope.new_perm.permission]
            if perm.valid_for_object_level
                return _object_list(perm.key)
            else
                return []
        else
            return []

    $scope.get_perm_object = (perm) ->
        _perm = $scope.get_perm(perm.csw_object_permission.csw_permission)
        # console.log perm, _perm
        if _perm.key not of $scope.obj_list_cache
            # build cache
            _object_list(_perm.key)
        _lut = $scope.obj_lut_cache[_perm.key]
        _pk = perm.csw_object_permission.object_pk
        if _pk of _lut
            return _lut[_pk].name
        else
            return "PK #{_pk} not found for #{_perm.key}"

    _enrich_permission = (perm) ->
        if $scope.type == "user"
            perm.user = $scope.user.idx
        else
            perm.group = $scope.group.idx

    # create / add functions
    $scope.create_permission = () ->
        # add new global permission
        _np = $scope.new_perm
        _new_p = {
            level: _np.level
            csw_permission: _np.permission
        }
        _enrich_permission(_new_p)
        if icswUserGroupTools.get_perm_fp(_new_p) not in (icswUserGroupTools.get_perm_fp(_old_p) for _old_p in $scope.permission_set)
            $scope.permission_set.push(_new_p)

    $scope.create_object_permission = () ->
        # add new object permission
        _np = $scope.new_perm
        _new_p = {
            level: _np.level
            csw_object_permission: {
                csw_permission: _np.permission
                object_pk: _np.object
            }
        }
        _enrich_permission(_new_p)
        if icswUserGroupTools.get_perm_fp(_new_p) not in (icswUserGroupTools.get_perm_fp(_old_p) for _old_p in $scope.object_permission_set)
            $scope.object_permission_set.push(_new_p)

    $scope.delete_permission = (perm) ->
        _fp = icswUserGroupTools.get_perm_fp(perm)
        _.remove($scope.permission_set, (entry) -> return _fp == icswUserGroupTools.get_perm_fp(entry))
        _.remove($scope.object_permission_set, (entry) -> return _fp == icswUserGroupTools.get_perm_fp(entry))

    $scope.changed = () ->
        return icswUserGroupTools.changed($scope.src_object)
    
    $scope.close = () ->
        $scope.$emit(ICSW_SIGNALS("_ICSW_CLOSE_USER_GROUP"), $scope.src_object, $scope.type)
        
    $scope.password_set = () ->
        if $scope.object.password.length
            return true
        else
            return false
            
    $scope.change_password = () ->
        icswUserGetPassword($scope, $scope.object).then(
            (done) ->
                if $scope.object.$$password_ok
                    # copy if password is now set
                    $scope.object.password = $scope.object.$$password
                    $scope.modify_ok = true
        )

]).directive("icswUserGroupPermissions",
[
    "$compile", "$templateCache",
(
    $compile, $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.group.permissions")
    }
]).directive("icswUserQuotaSettings",
[
    "$compile", "$templateCache", "icswTools",
(
    $compile, $templateCache, icswTools
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.quota.settings")
        scope:
            object: "=icswObject"
            object_type: "=icswObjectType"
            settings_tree: "=icswUserGroupSettingsTree"
        link: (scope, element, attrs) ->
            # console.log scope.object_type, scope.object
            if scope.object_type == "user"
                scope.quota_settings = scope.object.user_quota_setting_set
            else
                scope.quota_settings = scope.object.group_quota_setting_set

            _build_stacked = (qs, _type, abs) ->
                _used = qs["#{_type}_used"]
                _soft = qs["#{_type}_soft"]
                _hard = qs["#{_type}_hard"]
                r_stack = []
                if qs.$$qcb.size and (_soft or _hard)
                    if _type == "files"
                        _info1 = "files"
                        max_value = Math.max(_soft, _hard)
                        used_str = icswTools.get_size_str(_used, 1000, "")
                    else
                        _info1 = "space"
                        if abs
                            max_value = qs.$$qcb.size
                        else
                            max_value = _hard
                        used_str = icswTools.get_size_str(_used, 1024, "B")
                    if max_value > 0
                        _filled = parseInt(100 * _used / max_value)
                    else
                        _filled = 0
                    r_stack.push(
                        {
                            "value" : _filled
                            "type" : "success"
                            "out" : "#{_filled}%"
                            "title" : "#{_info1} used (#{used_str})"
                        }
                    )
                    if _used < _soft
                        # soft limit not reached
                        if max_value > 0
                            _lsoft = parseInt(100 * (_soft - _used) / max_value)
                        else
                            _lsoft = 0
                        if _type == "files"
                            lsoft_str = icswTools.get_size_str(_soft - _used, 1000, "")
                        else
                            lsoft_str = icswTools.get_size_str(_soft - _used, 1024, "B")
                        r_stack.push(
                            {
                                "value" : _lsoft
                                "type" : "warning"
                                "out": "#{_lsoft}%"
                                "title" : "#{_info1} left until soft limit is reached (#{lsoft_str})"
                            }
                        )
                        if _hard > _soft
                            if max_value > 0
                                _sth = parseInt(100 * (_hard - _soft) / max_value)
                            else
                                _sth = 0
                            if _type == "files"
                                sth_str = icswTools.get_size_str(_hard - _soft, 1000, "")
                            else
                                sth_str = icswTools.get_size_str(_hard - _soft, 1024, "B")
                            r_stack.push(
                                {
                                    "value" : _sth
                                    "type" : "info"
                                    "out": "#{_sth}%"
                                    "title" : "difference from soft to hard limit (#{sth_str})"
                                }
                            )
                    else
                        # soft limit reached
                        if max_value > 0
                            _lhard = parseInt(100 * (_hard - _used) / max_value)
                        else
                            _lhard = 0
                        if _type == "files"
                            sth_str = icswTools.get_size_str(_hard - _used, 1000, "")
                        else
                            sth_str = icswTools.get_size_str(_hard - _used, 1024, "B")
                        r_stack.push(
                            {
                                "value" : _lhard
                                "type" : if _soft then "danger" else "warning"
                                "out": "#{_lhard}%"
                                "title" : "#{_info1} left until hard limit is reached (#{sth_str})"
                            }
                        )
                return r_stack

            _get_line_class = (qs) ->
                if (qs.bytes_hard and qs.bytes_used > qs.bytes_hard) or (qs.files_hard and qs.files_used > qs.files_hard)
                    _class = "danger"
                else if (qs.bytes_soft and qs.bytes_used > qs.bytes_soft) or (qs.files_soft and qs.files_used > qs.files_soft)
                    _class = "warning"
                else
                    _class = ""
                return _class

            _get_bytes_limit = (qs) ->
                if qs.bytes_soft or qs.bytes_hard
                    return icswTools.get_size_str(qs.bytes_soft, 1024, "B") + " / " + icswTools.get_size_str(qs.bytes_hard, 1024, "B")
                else
                    return "---"

            _get_files_limit = (qs) ->
                if qs.files_soft or qs.files_hard
                    return icswTools.get_size_str(qs.files_soft, 1000, "") + " / " + icswTools.get_size_str(qs.files_hard, 1000, "")
                else
                    return "---"

            _salt_list = (in_list) ->
                for entry in in_list
                    entry.$$show_abs = false
                    # link
                    entry.$$qcb = scope.settings_tree.quota_capable_blockdevice_lut[entry.quota_capable_blockdevice]
                    entry.$$bytes_quota = if (entry.bytes_soft or entry.bytes_hard) then true else false
                    entry.$$files_quota = if (entry.files_soft or entry.files_hard) then true else false
                    # build stack
                    entry.$$files_stacked = _build_stacked(entry, "files", true)
                    entry.$$bytes_stacked_abs = _build_stacked(entry, "bytes", true)
                    entry.$$bytes_stacked_rel = _build_stacked(entry, "bytes", false)
                    entry.$$line_class = _get_line_class(entry)
                    entry.$$bytes_limit = _get_bytes_limit(entry)
                    entry.$$files_limit = _get_files_limit(entry)

            _salt_list(scope.quota_settings)

    }
]).directive("icswUserDiskUsage", ["$compile", "$templateCache", "icswTools", "icswDiskUsageTree", ($compile, $templateCache, icswTools, icswDiskUsageTree) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.disk.usage")
        link: (scope, element, attrs) ->
            scope.object = undefined
            scope.scan_runs = []
            scope.current_scan_run = null
            scope.du_tree = null
            scope.show_dots = false
            scope.icswTools = icswTools
            scope.$watch(attrs["object"], (new_val) ->
                scope.object = new_val
                scope.type = attrs["type"]
                if scope.object?
                    scope.current_scan_run = null
                    # salt list
                    if scope.type == "user"
                        scope.scan_runs = scope.object.user_scan_run_set
                        _valid = (_entry for _entry in scope.scan_runs when _entry.current == true)
                        if _valid.length
                            scope.current_scan_run = _valid[0]
                            # build tree
                            scope.build_tree()
            )
            scope.toggle_dots = () ->
                scope.show_dots = !scope.show_dots
                scope.build_tree()
            scope.build_tree = () ->
                _run = scope.current_scan_run
                # remember current expansion state
                _expanded = []
                if scope.du_tree
                    scope.du_tree.iter((entry) ->
                        if entry.expand
                            _expanded.push(entry.obj.full_name)
                    )
                scope.du_tree = new icswDiskUsageTree(scope)
                scope.SIZE_LIMIT = 1024 * 1024
                _tree_lut = {}
                _rest_list = []
                # pk of entries not shown (for .dot handling)
                _ns_list = []
                nodes_shown = 0
                for entry in _run.user_scan_result_set
                    if entry.parent_dir and entry.size_total < scope.SIZE_LIMIT
                        _ns_list.push(entry.idx)
                        continue
                    if not scope.show_dots and entry.name[0] == "."
                        _ns_list.push(entry.idx)
                        continue
                    if entry.parent_dir in _ns_list
                        _ns_list.push(entry.idx)
                        continue
                    nodes_shown++
                    t_entry = scope.du_tree.new_node(
                        folder: false
                        obj: entry
                        expand: entry.full_name in _expanded
                        always_folder: true
                    )
                    _tree_lut[entry.idx] = t_entry
                    if entry.parent_dir
                        _rest_list.push(t_entry)
                    else
                        scope.du_tree.add_root_node(t_entry)
                for entry in _rest_list
                    _tree_lut[entry.obj.parent_dir].add_child(entry)
                scope.nodes_shown = nodes_shown
            scope.scan_run_info = () ->
                if scope.scan_runs.length
                    _r_field = []
                    if scope.scan_runs.length > 1
                        _r_field.push("#{scope.scan_runs.length} runs")
                    if scope.current_scan_run
                        _run = scope.current_scan_run
                        _rundate = moment(_run.date)
                        _r_field.push("disk usage from #{_rundate.format(DT_FORM)} (#{_rundate.fromNow()})")
                        _r_field.push("took #{_run.run_time / 1000} seconds")
                        _r_field.push("scan depth is #{_run.scan_depth}")
                        _r_field.push("showing #{scope.nodes_shown} of #{_run.user_scan_result_set.length} nodes")
                        _r_field.push("size limit is " + icswTools.get_size_str(scope.SIZE_LIMIT, 1024, "B"))
                    return _r_field.join(", ")
                else
                    return "no scan runs"
    }
]).directive("icswUserVirtualDesktopSettings",
[
    "$compile", "$templateCache", "icswTools", "toaster",
(
    $compile, $templateCache, icswTools, toaster
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.user.vdu.settings")
        scope:
            user: "=icswUser"
            tree: "=icswUserGroupTree"
            device_tree: "=icswDeviceTree"
            settings_tree: "=icswUserGroupSettingsTree"
        link: (scope, element, attrs) ->

            scope.available_screen_sizes = available_screen_sizes
            scope.current_vdus = null
            scope.get_virtual_desktop_submit_mode = () ->
                if scope.current_vdus == null
                    return "create"
                else
                    return "modify"
            scope.cancel_virtual_desktop_user_setting = () ->
                scope.$apply(
                    scope._edit_obj.device = undefined
                )
                scope.current_vdus = null

            # build virtual desktop device list
            _build_vd_list = () ->
                vd_devs = []
                for vd in scope.settings_tree.virtual_desktop_protocol_list
                    for dev_index in vd.devices
                        vd_devs.push(dev_index)

                wm_devs = []
                for wm in scope.settings_tree.window_manager_list
                    for dev_index in wm.devices
                        wm_devs.push(dev_index)

                # vd_devs and wm_devs contain duplicates, but we dont care
                # devices which support both some kind of virtual desktop and window manager
                inter = _.intersection(vd_devs, wm_devs)
                _list = (scope.device_tree.all_lut[dev] for dev in inter)
                return (entry for entry in _list when not entry.is_meta_device)

            scope.virtual_desktop_devices = _build_vd_list()

            scope.virtual_desktop_device_available = scope.virtual_desktop_devices.length > 0

            scope.get_available_window_managers = (dev_index) ->
                if dev_index
                    return (wm for wm in scope.window_manager when (dev_index in wm.devices))
                else
                    return []

            scope.get_available_virtual_desktop_protocols = (dev_index) ->
                if dev_index
                    return (vd for vd in scope.virtual_desktop_protocol when (dev_index in vd.devices))
                else
                    return []

            scope.get_selected_screen_size_as_string = () ->
                if not scope._edit_obj.screen_size
                    return ""
                if scope._edit_obj.screen_size.manual
                    return scope._edit_obj.manual_screen_size_x + "x" + scope._edit_obj.manual_screen_size_y
                else
                    return scope._edit_obj.screen_size.name

            scope.create_virtual_desktop_user_setting = () ->
                # also called on modify
                new_obj = {
                    "window_manager": scope._edit_obj.window_manager
                    "virtual_desktop_protocol": scope._edit_obj.virtual_desktop_protocol
                    "screen_size": scope.get_selected_screen_size_as_string()
                    "device": scope._edit_obj.device
                    "user": scope._edit_obj.idx
                    "port": scope._edit_obj.port
                    "websockify_port": scope._edit_obj.websockify_port
                    "is_running": scope._edit_obj.start_automatically
                }
                if scope.get_virtual_desktop_submit_mode() == "create"
                    scope.push_virtual_desktop_user_setting(new_obj, (data) ->
                        scope._edit_obj.device = undefined
                        # also add locally
                        scope.virtual_desktop_user_setting.push(data)
                        toaster.pop("success", "", "added virtual desktop setting")
                    )
                else
                    # modify
                    for prop, val of new_obj
                        scope.current_vdus[prop] = val
                    scope.current_vdus.put()
                    # this should be patch, but is currently not supported
                    # scope.current_vdus.patch(new_obj)
                    scope.current_vdus = null # changes back to create mode
                    scope._edit_obj.device = undefined

            scope.on_device_change = () ->
                # set default values
                scope._edit_obj.port = 0 # could perhaps depend on protocol
                scope._edit_obj.websockify_port = 0 # could perhaps depend on protocol
                scope._edit_obj.screen_size = available_screen_sizes[1] # first is "manual"

                dev_index = scope._edit_obj.device
                wms = scope.get_available_window_managers(dev_index)
                if wms
                    scope._edit_obj.window_manager = wms[0].idx
                vds = scope.get_available_virtual_desktop_protocols(dev_index)
                if vds
                    scope._edit_obj.virtual_desktop_protocol = vds[0].idx

                scope._edit_obj.start_automatically = false

            scope.delete_virtual_desktop_user_setting = (vdus) ->
                vdus["to_delete"] = true
                #vdus.remove()
                vdus.put().then(() ->
                    # also remove locally
                    index = scope.virtual_desktop_user_setting.indexOf(vdus)
                    scope.virtual_desktop_user_setting.splice(index, 1)
                    toaster.pop("warning", "", "removed virtual desktop setting")
                )
            scope.modify_virtual_desktop_user_setting = (vdus) ->
                scope._edit_obj.device = vdus.device # this triggers the default settings, but we overwrite them hre
                # this changes the mode to modify mode
                scope.current_vdus = vdus

                # set initial data from vdus
                scope._edit_obj.port = vdus.port
                scope._edit_obj.websockify_port = vdus.websockify_port
                scope._edit_obj.screen_size = available_screen_sizes.filter((x) -> x.name == vdus.screen_size)[0]

                scope._edit_obj.window_manager = vdus.window_manager
                scope._edit_obj.virtual_desktop_protocol = vdus.virtual_desktop_protocol

                scope._edit_obj.start_automatically = vdus.is_running
    }
])

virtual_desktop_utils = {
    get_viewer_command_line: (vdus, ip) ->
        return "echo \"#{vdus.password}\" | vncviewer -autopass #{ip}:#{vdus.effective_port }\n"
}
