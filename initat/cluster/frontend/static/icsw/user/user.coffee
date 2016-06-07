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
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.useraccount", {
            url: "/useraccount"
            templateUrl: "icsw/main/user/account.html"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Account info"
        }
    )
    $stateProvider.state(
        "main.usertree", {
            url: "/usertree"
            templateUrl: "icsw/main/user/tree.html"
            icswData: icswRouteExtensionProvider.create
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
            if object.$$ignore_changes?
                return false
            else if object.$$changed?
                return true
            else if object.$$_ICSW_backup_def?
                # may be none during updates
                return object.$$_ICSW_backup_def.changed(object)
            else
                return false

    }
]).service("icswUser", 
[
    "$q", "Restangular", "ICSW_URLS",
(
    $q, Restangular, ICSW_URLS,
) ->
    class icswUser
        constructor: (user) ->
            @user = undefined
            @update(user)

        update: (user) =>
            # user is in fact a list with only one element
            # (to simplify the framework layers)
            @user = user[0]
            @build_luts()

        update_user: () =>
            _defer = $q.defer()
            if @user
                _update_url = ICSW_URLS.REST_USER_DETAIL.slice(1).slice(0, -2)
                Restangular.restangularizeElement(null, @user, _update_url)
                @user.put().then(
                    (ok) ->
                        @build_luts()
                        _defer.resolve("updated")
                    (not_ok) ->
                        _defer.reject("error updating")
                )
            else
                _defer.reject("no user")
            return _defer.promise

        build_luts: () =>
            # create luts (for vars)
            @var_lut = _.keyBy(@user.user_variable_set, "name")
            # console.log @var_lut
        
        has_var: (name) =>
            return name of @var_lut
            
        get_var: (name, def_val=null) =>
            if @has_var(name)
                return @var_lut[name]
            else
                return def_val

        delete_var: (name) =>
            _del = $q.defer()
            if @has_var(name)
                _var = @get_var(name)
                Restangular.restangularizeElement(null, _var, ICSW_URLS.REST_USER_VARIABLE_DETAIL.slice(1).slice(0, -2))
                _var.remove().then(
                    (ok) =>
                        _.remove(@user.user_variable_set, (entry) -> return entry.idx == _var.idx)
                        @build_luts()
                        _del.resolve("removed")
                    (error) =>
                        _del.reject("not removed")
                )
            else
                _del.reject("var does not exist")
            return _del.promise

        set_string_var: (name, value) =>
            return @set_var(name, value, "s")
            
        set_json_var: (name, value) =>
            return @set_var(name, value, "j")

        set_integer_var: (name, value) =>
            return @set_var(name, value, "i")

        get_var_names: (cur_re) =>
            return (key for key of @var_lut when key.match(cur_re))
            
        set_var: (name, value, var_type) =>
            # modify var (if exists) otherwise create new
            _wait = $q.defer()
            _result = $q.defer()
            if name of @var_lut
                _var= @get_var(name)
                _wait.resolve(_var)
            else
                new_var = {
                    user: @user.idx
                    name: name
                    var_type: var_type
                    hidden: false
                    editable: true
                }
                if var_type == "j"
                    new_var.json_value = value
                else
                    new_var.value = value
                    
                Restangular.all(
                    ICSW_URLS.REST_USER_VARIABLE_LIST.slice(1)
                ).post(
                    new_var
                ).then(
                    (nv) ->
                        console.log "new var=", nv
                        _wait.resolve(nv)
                )
            _wait.promise.then(
                (_var) =>
                    if _var.var_type != var_type
                        console.error "trying to change var_type for '#{_var.name}'' from '#{_var.var_type}' to '#{var_type}'"
                        _result.reject("wrong type")
                    else
                        if var_type == "j"
                            _var.json_value = value
                            _var.value = ""
                        else
                            _var.value = value
                            _var.json_value = ""
                        Restangular.restangularizeElement(null, _var, ICSW_URLS.REST_USER_VARIABLE_DETAIL.slice(1).slice(0, -2))
                        _var.put({"silent": 1}).then(
                            (new_var) =>
                                if new_var.name not of @var_lut
                                    @user.user_variable_set.push(new_var)
                                    @build_luts()
                                _result.resolve(new_var)
                            (not_ok) ->
                                _result.reject("not modifed")
                        )
            )

]).service("icswUserService",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "$rootScope", "ICSW_SIGNALS",
    "Restangular", "icswUser", "icswTreeBase",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, $rootScope, ICSW_SIGNALS,
    Restangular, icswUser, icswTreeBase,
) ->
    class icswUserService extends icswTreeBase
        get: () =>
            return @get_result()

        user_present: () =>
            console.log "UP called"
            return @is_valid()

        logout: () =>
            q = $q.defer()
            @clear_result()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.SESSION_LOGOUT
                    dataType: "json"
                }
            ).then(
                (json) ->
                    q.resolve(json)
            )
            return q.promise

        force_logout: () =>
            @cancel_pending_load()
            return @logout()

        update: () =>
            return @get_result().update_user()

    return new icswUserService(
        "User"
        icswUser
        [
            ICSW_URLS.SESSION_GET_AUTHENTICATED_USER
        ]
        "ICSW_USER_CHANGED"
    )
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
        load: (client) ->
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
    "$q", "Restangular", "ICSW_URLS", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $rootScope, ICSW_SIGNALS,
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
            # create user long names
            for user in @user_list
                if user.first_name and user.last_name
                    _fn = "#{user.login} (#{user.first_name} #{user.last_name})"
                else if user.first_name
                    _fn = "#{user.login} (#{user.first_name})"
                else if user.last_name
                    _fn = "#{user.login} (#{user.last_name})"
                else
                    _fn = "#{user.login}"
                user.$$long_name = _fn

        # remove / delete calls
        delete_user: (user) =>
            defer = $q.defer()
            _del_url = ICSW_URLS.REST_USER_DETAIL.slice(1).slice(0, -2)
            Restangular.restangularizeElement(null, user, _del_url)
            user.remove().then(
                (del) =>
                    _.remove(@user_list, (entry) -> return entry.idx == user.idx)
                    _.remove(@vdus_list, (entry) -> return entry.user == user.idx)
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve("deleted")
                (not_del) =>
                    defer.reject("not del")
            )
            return defer.promise

        delete_group: (group) =>
            defer = $q.defer()
            _del_url = ICSW_URLS.REST_GROUP_DETAIL.slice(1).slice(0, -2)
            Restangular.restangularizeElement(null, group, _del_url)
            group.remove().then(
                (del) =>
                    _del_users = _.remove(@group_list, (entry) -> return entry.idx == group.idx)
                    _del_user_ids = (user.idx for user in _del_users)
                    _.remove(@user_list, (entry) -> return entry.idx in _del_user_ids)
                    _.remove(@vdus_list, (entry) -> return entry.user in _del_user_ids)
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve("deleted")
                (not_del) =>
                    defer.reject("not del")
            )
            return defer.promise

        # create calls for users and groups

        create_user: (new_user) ->
            defer = $q.defer()
            _create_url = ICSW_URLS.REST_USER_LIST.slice(1)
            Restangular.all(_create_url).post(new_user).then(
                (created_user) =>
                    @user_list.push(created_user)
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve(created_user)
                (not_ok) =>
                    defer.reject("not saved")
            )
            return defer.promise

        create_group: (new_group) ->
            defer = $q.defer()
            _create_url = ICSW_URLS.REST_GROUP_LIST.slice(1)
            Restangular.all(_create_url).post(new_group).then(
                (created_group) =>
                    @group_list.push(created_group)
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve(created_group)
                (not_ok) =>
                    defer.reject("not saved")
            )
            return defer.promise

        # modify calls for users and groups

        modify_user: (user) ->
            defer = $q.defer()
            _modify_url = ICSW_URLS.REST_USER_DETAIL.slice(1).slice(0, -2)
            Restangular.restangularizeElement(null, user, _modify_url)
            user.put().then(
                (saved_user) =>
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve("saved")
                (not_ok) =>
                    defer.reject("not saved")
            )
            return defer.promise

        modify_group: (group) ->
            defer = $q.defer()
            _modify_url = ICSW_URLS.REST_GROUP_DETAIL.slice(1).slice(0, -2)
            Restangular.restangularizeElement(null, group, _modify_url)
            group.put().then(
                (saved_group) =>
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve("saved")
                (not_ok) =>
                    defer.reject("not saved")
            )
            return defer.promise

        modify_user_permissions: (user, add_perms, rem_perms) ->
            return @_modify_perms(user, add_perms, rem_perms, "user", "user_permission")

        modify_user_object_permissions: (user, add_perms, rem_perms) ->
            return @_modify_perms(user, add_perms, rem_perms, "user", "user_object_permission")

        modify_group_permissions: (group, add_perms, rem_perms) ->
            return @_modify_perms(group, add_perms, rem_perms, "group", "group_permission")

        modify_group_object_permissions: (group, add_perms, rem_perms) ->
            return @_modify_perms(group, add_perms, rem_perms, "group", "group_object_permission")

        _modify_perms: (object, add_perms, rem_perms, obj_type, perm_type) =>
            defer = $q.defer()
            _modify_url = ICSW_URLS["REST_" + _.toUpper(perm_type) + "_DETAIL"].slice(1).slice(0, -2)
            _create_url = ICSW_URLS["REST_" + _.toUpper(perm_type) + "_LIST"].slice(1)
            (Restangular.restangularizeElement(null, rem_perm, _modify_url) for rem_perm in rem_perms)
            # salt perms and build calls
            _calls = []
            _call_info = []
            for add_perm in add_perms
                add_perm[obj_type] = object.idx
                _calls.push(Restangular.all(_create_url).post(add_perm))
                _call_info.push(["add", add_perm])
            for rem_perm in rem_perms
                rem_perm[obj_type] = object.idx
                _calls.push(rem_perm.remove())
                _call_info.push(["rem", rem_perm])
            $q.allSettled(
                _calls
            ).then(
                (data) ->
                    for [res_info, [info_str, info_obj]] in _.zip(data, _call_info)
                        if info_str == "add"
                            object["#{perm_type}_set"].push(res_info.value)
                        else
                            _.remove(object["#{perm_type}_set"], (entry) -> return entry.idx == info_obj.idx)
                    defer.resolve("done")
            )
            return defer.promise

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
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->
    class icswUserGroupDisplayTree extends icswReactTreeConfig
        constructor: (@scope, args) ->
            super(args)
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

        handle_click: (event, entry) =>
            @clear_active()
            entry.set_active(true)
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

]).service("icswDiskUsageTree",
[
    "icswReactTreeConfig",
(
    icswReactTreeConfig
) ->
    class icsw_disk_usage_tree extends icswReactTreeConfig
        constructor: (@scope, args) ->
            super(args)

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
    "icswSimpleAjaxCall", "ICSW_URLS", "$rootScope",
(
    icswUserGroupTreeService, $scope, $compile, $q, icswUserGroupSettingsTreeService, blockUI,
    icswUserGroupPermissionTreeService, icswUserGroupDisplayTree, $timeout, icswDeviceTreeService,
    icswUserBackup, icswGroupBackup, icswUserGroupTools, ICSW_SIGNALS, icswToolsSimpleModalService,
    icswSimpleAjaxCall, ICSW_URLS, $rootScope,
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
        display_tree: new icswUserGroupDisplayTree(
            $scope
            {
                show_selection_buttons: false
                show_icons: true
                show_select: false
                show_descendants: true
                show_childs: false
            }
        )
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

        $rootScope.$on(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"), (event) ->
            $scope.rebuild_tree()
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
                t_entry = _dt.create_node(
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
                t_entry = _dt.create_node(
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
            $$changed: true
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
            $$changed: true
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
]).controller("icswUserAccountCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular",
    "$q", "$timeout", "$uibModal", "ICSW_URLS", "icswUserService",
    "icswUserGroupSettingsTreeService", "icswUserGroupPermissionTreeService",
    "icswUserGetPassword", "blockUI",
(
    $scope, $compile, $filter, $templateCache, Restangular,
    $q, $timeout, $uibModal, ICSW_URLS, icswUserService,
    icswUserGroupSettingsTreeService, icswUserGroupPermissionTreeService,
    icswUserGetPassword, blockUI,
) ->
    $scope.struct = {
        data_valid: false
        user: undefined
        settings_tree: undefined
    }
    # for permission view, FIXME, ToDo
    $scope.perm_tree = undefined

    $scope.get_perm = (perm) ->
        return $scope.perm_tree.permission_lut[perm]

    $scope.update = () ->
        $scope.struct.data_valid = false
        $scope.struct.user = undefined
        $scope.struct.settings_tree = undefined
        $scope.permission_set = []
        $scope.object_permission_set = []
        $q.all(
            [
                icswUserService.load()
                icswUserGroupSettingsTreeService.load($scope.$id)
                icswUserGroupPermissionTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.data_valid = true
                $scope.struct.user = data[0].user
                $scope.struct.settings_tree = data[1]
                $scope.perm_tree = data[2]
                # hack, to be improved, FIXME, ToDo
                $scope.permission_set = $scope.struct.user.user_permission_set
                $scope.object_permission_set = $scope.struct.user.user_object_permission_set
        )

    $scope.change_password = () ->
        icswUserGetPassword($scope, $scope.struct.user).then(
            (done) ->
                if $scope.struct.user.$$password_ok
                    # copy if password is now set
                    $scope.struct.user.password = $scope.struct.user.$$password
                    $scope.update_account()
        )

    $scope.update_account = () ->
        blockUI.start("saving account changes")
        icswUserService.update().then(
           (data) ->
               blockUI.stop()
           (resp) ->
               blockUI.stop()
        )

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
    "blockUI", "icswSimpleAjaxCall", "ICSW_URLS"
(
    $scope, $q, icswUserGroupTools, ICSW_SIGNALS, icswToolsSimpleModalService, icswUserGetPassword,
    blockUI, icswSimpleAjaxCall, ICSW_URLS
) ->

    $scope.obj_list_cache = {}
    $scope.obj_lut_cache = {}

    $scope.new_perm = {
        permission: undefined
        level: 0
        object: undefined
    }

    _set_permissions_from_src = () ->
        $scope.object = $scope.src_object.$$_ICSW_backup_data
        if $scope.type == "user"
            $scope.permission_set = $scope.object.user_permission_set
            $scope.object_permission_set = $scope.object.user_object_permission_set
        else
            $scope.permission_set = $scope.object.group_permission_set
            $scope.object_permission_set = $scope.object.group_object_permission_set

    $scope.set_type = (ug_type) ->
        $scope.type = ug_type
        if $scope.type == "user"
            # original
            $scope.src_object = $scope.user
            # working object
            _set_permissions_from_src()
            # check password
            if $scope.user.password.length
                $scope.modify_ok = true
            else
                $scope.modify_ok = false
        else
            # original
            $scope.src_object = $scope.group
            # working object
            _set_permissions_from_src()
        if $scope.object.idx?
            $scope.create_mode = false
        else
            $scope.create_mode = true

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

    # _enrich_permission = (perm) ->
    #    if $scope.type == "user"
    #        perm.user = $scope.user.idx
    #    else
    #        perm.group = $scope.group.idx

    # create / add functions
    $scope.create_permission = () ->
        # add new global permission
        _np = $scope.new_perm
        _new_p = {
            level: _np.level
            csw_permission: _np.permission
        }
        # _enrich_permission(_new_p)
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
        # _enrich_permission(_new_p)
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

    $scope.delete = () ->
        # check for deletion of own user / group, TODO, FIXME
        icswToolsSimpleModalService("Really delete #{$scope.type} ?").then(
            (doit) ->
                blockUI.start("deleting #{$scope.type}")
                defer = $q.defer()
                $scope.tree["delete_#{$scope.type}"]($scope.object).then(
                    (deleted) ->
                        defer.resolve("ok")
                    (not_del) ->
                        defer.reject("not del")
                )
                defer.promise.then(
                    (removed) ->
                        blockUI.stop()
                        $scope.src_object.$$ignore_changes = true
                        $scope.$emit(ICSW_SIGNALS("_ICSW_CLOSE_USER_GROUP"), $scope.src_object, $scope.type)
                    (not_rem) ->
                        blockUI.stop()
                )
        )
        
    # create / modify functions
    $scope.modify = () ->
        # copy data to original object
        bu_def = $scope.src_object.$$_ICSW_backup_def

        # lists of permissions to delete / create
        perm_name = "#{$scope.type}_permission_set"
        cur_perms = (icswUserGroupTools.get_perm_fp(_perm) for _perm in $scope.src_object[perm_name])
        new_perms = (icswUserGroupTools.get_perm_fp(_perm) for _perm in $scope.src_object.$$_ICSW_backup_data[perm_name])
        perms_to_create = (entry for entry in $scope.src_object.$$_ICSW_backup_data[perm_name] when icswUserGroupTools.get_perm_fp(entry) not in cur_perms)
        perms_to_remove = (entry for entry in $scope.src_object[perm_name] when icswUserGroupTools.get_perm_fp(entry) not in new_perms)

        # lists of object permissions to delete / create
        obj_perm_name = "#{$scope.type}_object_permission_set"
        cur_obj_perms = (icswUserGroupTools.get_perm_fp(_perm) for _perm in $scope.src_object[obj_perm_name])
        new_obj_perms = (icswUserGroupTools.get_perm_fp(_perm) for _perm in $scope.src_object.$$_ICSW_backup_data[obj_perm_name])
        obj_perms_to_create = (entry for entry in $scope.src_object.$$_ICSW_backup_data[obj_perm_name] when icswUserGroupTools.get_perm_fp(entry) not in cur_obj_perms)
        obj_perms_to_remove = (entry for entry in $scope.src_object[obj_perm_name] when icswUserGroupTools.get_perm_fp(entry) not in new_obj_perms)

        # console.log perms_to_create, perms_to_remove
        # console.log obj_perms_to_create, obj_perms_to_remove
        # save current settings
        saved_perms = $scope.src_object[perm_name]
        saved_obj_perms = $scope.src_object[obj_perm_name]

        # copy to backup object to disable partial backup
        $scope.src_object.$$_ICSW_backup_data[perm_name] = saved_perms
        $scope.src_object.$$_ICSW_backup_data[obj_perm_name] = saved_obj_perms

        # restore backup
        bu_def.restore_backup($scope.src_object)

        blockUI.start("updating #{$scope.type} object")
        defer = $q.defer()

        if $scope.create_mode
            # create new object
            $scope.tree["create_#{$scope.type}"]($scope.src_object).then(
                (created) ->
                    $scope.src_obejct = created
                    defer.resolve("created")
                (not_saved) ->
                    defer.reject("not created")
            )
        else
            $scope.tree["modify_#{$scope.type}"]($scope.src_object).then(
                (saved) ->
                    defer.resolve("saved")
                (not_saved) ->
                    defer.reject("not saved")
            )
        defer.promise.then(
            (ok) ->
                $q.all(
                    [
                        $scope.tree["modify_#{$scope.type}_permissions"]($scope.src_object, perms_to_create, perms_to_remove)
                        $scope.tree["modify_#{$scope.type}_object_permissions"]($scope.src_object, obj_perms_to_create, obj_perms_to_remove)
                    ]
                ).then(
                    (done) ->
                        # create new backup
                        bu_def.create_backup($scope.src_object)
                        $scope.object = $scope.src_object.$$_ICSW_backup_data
                        _set_permissions_from_src()
                        if $scope.create_mode
                            # close current tab
                            $scope.src_object.$$ignore_changes = true
                            $scope.$emit(ICSW_SIGNALS("_ICSW_CLOSE_USER_GROUP"), $scope.src_object, $scope.type)
                        blockUI.stop()
                )
            (not_ok) ->
                # create new backup
                bu_def.create_backup($scope.src_object)
                $scope.object = $scope.src_object.$$_ICSW_backup_data
                _set_permissions_from_src()
                blockUI.stop()
        )

        
    # password functions

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
        
    $scope.generate_2fa = () ->
        icswSimpleAjaxCall({
            url: ICSW_URLS.USER_GENERATE_NEW_2FA_SECRET
            data:
                idx: $scope.src_object.idx
            dataType: 'json'
        }).then(
            (result) =>
                $scope.user.totp_provisioning_uri = result['new_uri']
        )
        
    $scope.remove_2fa = () ->
        icswSimpleAjaxCall({
            url: ICSW_URLS.USER_REMOVE_2FA_SECRET
            data:
                idx: $scope.src_object.idx
            dataType: 'json'
        }).then(
            (result) =>
                $scope.user.totp_provisioning_uri = result['new_uri']
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
            scope.$watch("object", (new_val) ->
                if new_val
                    if scope.object_type == "user"
                        scope.quota_settings = scope.object.user_quota_setting_set
                    else
                        scope.quota_settings = scope.object.group_quota_setting_set
                    _salt_list(scope.quota_settings)
                else
                    scope.quota_settings = []
            )

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

    }
]).directive("icswUserDiskUsage",
[
    "$compile", "$templateCache", "icswTools", "icswDiskUsageTree",
(
    $compile, $templateCache, icswTools, icswDiskUsageTree,
) ->
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
                scope.du_tree = new icswDiskUsageTree(
                    scope
                    {
                        show_selection_buttons: false
                        show_icons: true
                        show_select: false
                        show_descendants: true
                        show_childs: false
                    }
                )
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
                    t_entry = scope.du_tree.create_node(
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
