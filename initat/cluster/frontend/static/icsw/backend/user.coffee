# Copyright (C) 2012-2017 init.at
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
# along with this program; if not, write to the Free Softwareo
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

DT_FORM = "YYYY-MM-DD HH:mm"

angular.module(
    "icsw.backend.user",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "noVNC", "ui.select", "icsw.tools", "icsw.user.password", "icsw.layout.theme",
    ]
).service("icswUserGroupRoleTools",
[
    "$q",
(
    $q,
) ->
    struct = {
        obj_list_cache: {}
        obj_lut_cache: {}
    }

    clean_cache = () ->
        struct.obj_list_cache = {}
        struct.obj_lut_cache = {}

    get_cache = (key, device_tree, ugs_tree) ->
        if key not of struct.obj_list_cache
            _list = []
            if key == "backbone.device"
                for entry in device_tree.enabled_list
                    if entry.is_meta_device
                        if entry.is_cluster_device_group
                            _name = "[CDG] " + entry.$$print_name
                        else
                            _name = "[MD] " + entry.$$print_name
                    else
                        _name = entry.$$print_name
                    _list.push(
                        {
                            idx: entry.idx
                            name: _name
                            group: "DeviceGroup " + device_tree.group_lut[entry.device_group].name
                        }
                    )
            else if key == "backbone.user"
                for entry in ugs_tree.user_list
                    _list.push(
                        {
                            idx: entry.idx
                            name: entry.login
                            group: "Group " + ugs_tree.group_lut[entry.group].groupname
                        }
                    )
            else if key == "backbone.group"
                for entry in ugs_tree.group_list
                    _list.push(
                        {
                            idx: entry.idx
                            name: entry.groupname
                            group: ""
                        }
                    )
            else if key == "backbone.device_group"
                for entry in device_tree.group_list
                    _list.push(
                        {
                            idx: entry.idx
                            name: entry.name
                            group: ""
                        }
                    )
            else
                console.error "unknown OLP-key '#{key}'"
            # console.log "***", key, (_e.name for _e in _list)
            struct.obj_list_cache[key] = _list
            struct.obj_lut_cache[key] = _.keyBy(_list, "idx")
        return struct.obj_list_cache[key]

    salt_user = (user) ->
        if user.first_name and user.last_name
            _fn = "#{user.login} (#{user.first_name} #{user.last_name})"
        else if user.first_name
            _fn = "#{user.login} (#{user.first_name})"
        else if user.last_name
            _fn = "#{user.login} (#{user.last_name})"
        else
            _fn = "#{user.login}"
        user.$$long_name = _fn
        if user.email
            user.$$user_email = "#{user.login} (#{user.email})"
        else
            user.$$user_email = "#{user.login} (N/A)"

    return {
        salt_user: (user) ->
            return salt_user(user)

        clean_cache: () ->
            return clean_cache()

        get_cache: (key, device_tree, ugs_tree) ->
            return get_cache(key, device_tree, ugs_tree)

        get_cache_lut: (key, device_tree, ugs_tree) ->
            get_cache(key, device_tree, ugs_tree)
            return struct.obj_lut_cache[key]

        # permission fingerprint
        get_perm_fp: (perm) ->
            if perm.csw_object_permission?
                return "#{perm.level}-#{perm.user}-#{perm.csw_object_permission.csw_permission}-#{perm.csw_object_permission.object_pk}"
            else
                return "#{perm.level}-#{perm.user}-#{perm.csw_permission}"

        pipe_spec_var_names: () ->
            # should be transferred from server, FIXME
            return [
                "$$network_topology_pipe"
                "$$livestatus_dashboard_pipe"
                "$$device_location_pipe"
            ]
    }
]).service("icswUser",
[
    "$q", "Restangular", "ICSW_URLS", "icswUserGroupRoleTools",
(
    $q, Restangular, ICSW_URLS, icswUserGroupRoleTools,
) ->
    class icswUser
        constructor: (user) ->
            @user = undefined
            @update(user)
            @init_vars()

        update: (user) =>
            # user is in fact a list with only one element
            # (to simplify the framework layers)
            @user = user[0]
            # dict of variable save requests, name -> list
            @__vars_to_save = {}
            icswUserGroupRoleTools.salt_user(@user)
            @build_luts()

        is_authenticated: () =>
            return @user.is_authenticated

        update_user: () =>
            _defer = $q.defer()
            if @user
                _update_url = ICSW_URLS.REST_USER_DETAIL.slice(1).slice(0, -2)
                Restangular.restangularizeElement(null, @user, _update_url)
                @user.put().then(
                    (ok) =>
                        @build_luts()
                        _defer.resolve("updated")
                    (not_ok) ->
                        _defer.reject("error updating")
                )
            else
                _defer.reject("no user")
            return _defer.promise

        init_vars: () =>
            @dc_var_name = @expand_var("$$device_class_filter")
            if @has_var(@dc_var_name)
                try
                    @__dc_filter = angular.fromJson(@get_var(@dc_var_name).json_value)
                catch error
                    @__dc_filter = {}
            else
                @__dc_filter = {}
                @_store_dc_filter()

        get_device_class_filter: () =>
            return angular.toJson(@__dc_filter)

        restore_device_class_filter: (in_json, dcf) =>
            @__dc_filter = angular.fromJson(in_json)
            if dcf.read_device_class_filter(@__dc_filter)
                @_store_dc_filter()

        read_device_class_filter: (dcf) =>
            # copies dc_filter settings to device_class_tree
            # dcf ... device_class_filter object
            if dcf.validate_device_class_filter(@__dc_filter)
                # somehting changed, store filter
                @_store_dc_filter()

        write_device_class_filter: (dcf) =>
            # syncs device var with device_class_tree $$enabled
            if dcf.write_device_class_filter(@__dc_filter)
                @_store_dc_filter()

        _store_dc_filter: () =>
            if @is_authenticated()
                @set_json_var(@dc_var_name, angular.toJson(@__dc_filter))

        build_luts: () =>
            # create luts (for vars)
            @var_lut = _.keyBy(@user.user_variable_set, "name")
            # console.log @var_lut
        
        has_var: (name) =>
            return name of @var_lut

        expand_var: (name) =>
            name = _.replace(name, "$$SESSIONID$$", @user.session_id)
            return name

        get_or_create: (name, def_val, var_type) =>
            defer = $q.defer()
            if @has_var(name)
                defer.resolve(@var_lut[name])
            else
                @set_var(name, def_val, var_type).then(
                    (ok) ->
                        console.log "OK=", ok
                        defer.resolve(ok)
                )
            return defer.promise

        get_var: (name, def_val=null) =>
            if @has_var(name)
                return @var_lut[name]
            else
                return {name: name, value: def_val, $$default: true}

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

        _handle_var: (name) =>
            _remove_latest = () =>
                # remove latest var
                @__vars_to_save[name].shift()
                if @__vars_to_save[name].length
                    # any requests left ?
                    @_handle_var(name)

            [name, value, var_type, _result] = @__vars_to_save[name][0]
            _wait = $q.defer()
            if name of @var_lut
                _var = @get_var(name)
                _wait.resolve(_var)
            else
                # create before update
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
                        console.log "create new user_variable: ", nv
                        _wait.resolve(nv)
                )
            _result = $q.defer()
            _wait.promise.then(
                (_var) =>
                    if _var.var_type != var_type
                        console.error "trying to change var_type for '#{_var.name}'' from '#{_var.var_type}' to '#{var_type}'"
                        _remove_latest()
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
                                if new_var.name of @var_lut
                                    _.remove(@user.user_variable_set, (entry) -> return entry.idx == new_var.idx)
                                @user.user_variable_set.push(new_var)
                                @build_luts()
                                _remove_latest()
                                _result.resolve(new_var)
                            (not_ok) =>
                                _remove_latest()
                                _result.reject("not modifed")
                        )
            )

        set_var: (name, value, var_type) =>
            # modify var (if exists) otherwise create new
            if name not of @__vars_to_save
                @__vars_to_save[name] = []
            _result = $q.defer()
            # save / store action for this var pending, buffer request
            @__vars_to_save[name].push(
                [
                    name
                    value
                    var_type
                    _result
                ]
            )
            if @__vars_to_save[name].length == 1
                @_handle_var(name)
            return _result.promise

]).service("icswUserService",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "$rootScope", "ICSW_SIGNALS",
    "Restangular", "icswUser", "icswTreeBase", "icswThemeService", "icswMenuSettings",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, $rootScope, ICSW_SIGNALS,
    Restangular, icswUser, icswTreeBase, icswThemeService, icswMenuSettings,
) ->
    class icswUserService extends icswTreeBase
        get: () =>
            return @get_result()

        user_present: () =>
            return @is_valid()

        logout: () =>
            q = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.SESSION_LOGOUT
                    dataType: "json"
                }
            ).then(
                (json) =>
                    @clear_result()
                    q.resolve(json)
            )
            return q.promise

        force_logout: () =>
            @cancel_pending_load()
            return @logout()

        get_load_signal: (result) =>
            if result.is_authenticated()
                # user is authenticated, send default signal
                return @signal
            else
                # not authenticated, no signal to send
                return null

        update_user: () =>
            # update user, called from account
            @new_data_set()
            result = @get_result()
            return result.update_user()

        new_data_set: () =>
            # called from icswTreeBase
            result = @get_result()
            # send theme to themeservice and menusetting
            if result.has_var("$$ICSW_THEME_SELECTION$$")
                icswThemeService.setcurrent(result.get_var("$$ICSW_THEME_SELECTION$$").value)
            if result.has_var("$$ICSW_MENU_LAYOUT_SELECTION$$")
                icswMenuSettings.set_menu_layout(result.get_var("$$ICSW_MENU_LAYOUT_SELECTION$$").value)

    return new icswUserService(
        "User"
        icswUser
        [
            ICSW_URLS.SESSION_GET_AUTHENTICATED_USER
        ]
        "ICSW_USER_LOGGEDIN"
        "ICSW_USER_LOGGEDOUT"
    )
]).service("icswUserGroupRolePermissionTree",
[
    "$q",
(
    $q,
) ->
    # permission list and objects
    class icswUserGroupRolePermissionTree
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

]).service("icswUserGroupRolePermissionTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswUserGroupRolePermissionTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswUserGroupRolePermissionTree, $rootScope, ICSW_SIGNALS,
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
                _result = new icswUserGroupRolePermissionTree(data[0], data[1])
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
]).service("icswUserGroupRoleSettingsTree",
[
    "$q",
(
    $q,
) ->
    # various settings for users and group
    class icswUserGroupRoleSettingsTree
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

]).service("icswUserGroupRoleSettingsTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswUserGroupRoleSettingsTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswUserGroupRoleSettingsTree, $rootScope, ICSW_SIGNALS,
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
                _result = new icswUserGroupRoleSettingsTree(data[0], data[1], data[2], data[3])
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
]).service("icswUserGroupRoleTree",
[
    "$q", "Restangular", "ICSW_URLS", "$rootScope", "ICSW_SIGNALS",
    "icswUserGroupRoleTools",
(
    $q, Restangular, ICSW_URLS, $rootScope, ICSW_SIGNALS,
    icswUserGroupRoleTools,
) ->
    # user / group tree representation
    class icswUserGroupRoleTree
        constructor: (user_list, group_list, role_list, vdus_list) ->
            @user_list =[]
            @group_list = []
            @role_list = []
            @vdus_list = []
            @update(user_list, group_list, role_list, vdus_list)

        update: (user_list, group_list, role_list, vdus_list) =>
            @role_list.length = 0
            for role in role_list
                @role_list.push(role)
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
            @role_lut = _.keyBy(@role_list, "idx")
            @link()

        link: () =>
            # link roles
            for role in @role_list
                for entry in role.rolepermission_set
                    entry.$$role = role
                for entry in role.roleobjectpermission_set
                    entry.$$role = role
            # create usefull links
            for vdus in @vdus_list
                @user_lut[vdus.user].vdus_list.push(vdus)
            # create user long names
            for user in @user_list
                icswUserGroupRoleTools.salt_user(user)

        # remove / delete calls
        delete_user: (user, already_deleted) =>
            defer = $q.defer()
            del_defer = $q.defer()
            if already_deleted
                del_defer.resolve("ok")
            else
                _del_url = ICSW_URLS.REST_USER_DETAIL.slice(1).slice(0, -2)
                Restangular.restangularizeElement(null, user, _del_url)
                user.remove().then(
                    (del) ->
                        del_defer.resolve("ok")
                    (not_del) ->
                        del_defer.reject("not ok")
                )
            del_defer.promise.then(
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

        delete_group: (group, already_deleted) =>
            defer = $q.defer()
            del_defer = $q.defer()
            if already_deleted
                del_defer.resolve("ok")
            else
                _del_url = ICSW_URLS.REST_GROUP_DETAIL.slice(1).slice(0, -2)
                Restangular.restangularizeElement(null, group, _del_url)
                group.remove().then(
                    (del) ->
                        del_defer.resolve("ok")
                    (not_del) ->
                        del_defer.reject("not ok")
                )
            del_defer.promise.then(
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

        delete_role: (role) =>
            defer = $q.defer()
            _del_url = ICSW_URLS.REST_ROLE_DETAIL.slice(1).slice(0, -2)
            Restangular.restangularizeElement(null, role, _del_url)
            role.remove().then(
                (del) =>
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve("deleted")
                (not_del) =>
                    defer.reject("not del")
            )
            return defer.promise

        # create calls for users and groups and roles

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

        create_role: (new_role) ->
            defer = $q.defer()
            _create_url = ICSW_URLS.REST_ROLE_LIST.slice(1)
            Restangular.all(_create_url).post(new_role).then(
                (created_role) =>
                    @role_list.push(created_role)
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve(created_role)
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

        modify_role: (role) ->
            defer = $q.defer()
            _modify_url = ICSW_URLS.REST_ROLE_DETAIL.slice(1).slice(0, -2)
            Restangular.restangularizeElement(null, role, _modify_url)
            role.put().then(
                (saved_role) =>
                    @build_luts()

                    # send signal
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))

                    defer.resolve("saved")
                (not_ok) =>
                    defer.reject("not saved")
            )
            return defer.promise

        modify_role_permissions: (role, add_perms, rem_perms) ->
            return @_modify_perms(role, add_perms, rem_perms, "role", "role_permission")

        modify_role_object_permissions: (role, add_perms, rem_perms) ->
            return @_modify_perms(role, add_perms, rem_perms, "role", "role_object_permission")

        _modify_perms: (object, add_perms, rem_perms, obj_type, perm_type) =>
            defer = $q.defer()
            # only working for role
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
                (data) =>
                    for [res_info, [info_str, info_obj]] in _.zip(data, _call_info)
                        _perm_type = _.replace(_.replace(perm_type, "_", ""), "_", "")
                        if info_str == "add"
                            object["#{_perm_type}_set"].push(res_info.value)
                        else
                            _.remove(object["#{_perm_type}_set"], (entry) -> return entry.idx == info_obj.idx)
                    @build_luts()
                    $rootScope.$emit(ICSW_SIGNALS("ICSW_USER_GROUP_TREE_CHANGED"))
                    defer.resolve("done")
            )
            return defer.promise

]).service("icswUserGroupRoleTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall",
    "icswTools", "icswUserGroupRoleTree", "$rootScope", "ICSW_SIGNALS",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall,
    icswTools, icswUserGroupRoleTree, $rootScope, ICSW_SIGNALS,
) ->
    rest_map = [
        [
            ICSW_URLS.REST_USER_LIST, {}
        ]
        [
            ICSW_URLS.REST_GROUP_LIST, {}
        ]
        [
            ICSW_URLS.REST_ROLE_LIST, {}
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
                console.log "*** user/group/role tree loaded ***"
                _result = new icswUserGroupRoleTree(data[0], data[1], data[2], data[3])
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
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
])
