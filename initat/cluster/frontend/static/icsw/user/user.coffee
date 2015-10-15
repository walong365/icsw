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
).service("icswUserService", ["$q", "ICSW_URLS", "icswSimpleAjaxCall", ($q, ICSW_URLS, icswSimpleAjaxCall) ->
    _last_load = 0
    _user = undefined
    load_data = (cache) ->
        cur_time = moment().unix()
        _diff_time = Math.abs(cur_time - _last_load)
        _defer = $q.defer()
        if _diff_time > 5 or not cache
            icswSimpleAjaxCall(
                url: ICSW_URLS.SESSION_GET_USER,
                dataType: "json"
            ).then((data) ->
                _last_load = moment().unix()
                _user = data
                _defer.resolve(data)
            )
        else
            _defer.resolve(_user)
        return _defer
    return {
        "load": (cache) ->
            # loads from server
            return load_data(cache).promise
        "get": () ->
            return _user
    }
]).service("icswUserTree", ["icswTreeConfig", (icswTreeConfig) ->
    class icsw_user_tree extends icswTreeConfig
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = true
            @show_select = false
            @show_descendants = true
            @show_childs = false
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
        handle_click: (entry, event) =>
            @clear_active()
            entry.active = true
            @scope.edit_object(entry.obj, entry._node_type)
            @scope.$digest()
]).service("icswDiskUsageTree", ["icswTreeConfig", (icswTreeConfig) ->
    class icww_disk_usage_tree extends icswTreeConfig
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
]).controller("user_tree", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$timeout", "$modal", "blockUI", "ICSW_URLS", "icswSimpleAjaxCall", "toaster", "access_level_service", "icswUserTree",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $timeout, $modal, blockUI, ICSW_URLS, icswSimpleAjaxCall, toaster, access_level_service, icswUserTree) ->
        $scope.ac_levels = [
            {"level" : 0, "info" : "Read-only"},
            {"level" : 1, "info" : "Modify"},
            {"level" : 3, "info" : "Modify, Create"},
            {"level" : 7, "info" : "Modify, Create, Delete"},
        ]
        access_level_service.install($scope)
        $scope.obj_perms = {}
        $scope.tree = new icswUserTree($scope)
        $scope.filterstr = ""
        # init edit mixins
        $scope.group_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q)
        $scope.group_edit.modify_rest_url = ICSW_URLS.REST_GROUP_DETAIL.slice(1).slice(0, -2)
        $scope.group_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_GROUP_LIST.slice(1))
        $scope.group_edit.use_modal = false
        $scope.group_edit.change_signal = "icsw.user.groupchange"
        $scope.group_edit.new_object = () ->
            gid = 200
            gids = (entry.gid for entry in $scope.group_list)
            while gid in gids
                gid++
            r_obj = {
                "groupname" : "new_group"
                "gid" : gid
                "active" : true
                "homestart" : "/home"
                "perms" : []
                "group_quota_setting": []
            }
            return r_obj
        $scope.user_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q)
        $scope.user_edit.modify_rest_url = ICSW_URLS.REST_USER_DETAIL.slice(1).slice(0, -2)
        $scope.user_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_USER_LIST.slice(1))
        $scope.user_edit.use_modal = false
        $scope.user_edit.change_signal = "icsw.user.userchange"
        $scope.user_edit.new_object = () ->
            uid = 200
            uids = (entry.uid for entry in $scope.user_list)
            while uid in uids
                uid++
            r_obj = {
                "login" : "new_user"
                "uid" : uid
                "active" : true
                "db_is_auth_for_password" : true
                "group" : (entry.idx for entry in $scope.group_list)[0]
                "shell" : "/bin/bash"
                "perms" : []
                "scan_depth" : 2
                "user_quota_setting": []
            }
            return r_obj
        wait_list = restDataSource.add_sources([
            [ICSW_URLS.REST_GROUP_LIST, {}]
            [ICSW_URLS.REST_USER_LIST, {}]
            [ICSW_URLS.REST_DEVICE_GROUP_LIST, {}]
            [ICSW_URLS.REST_CSW_PERMISSION_LIST, {}]
            [ICSW_URLS.REST_HOME_EXPORT_LIST, {}]
            [ICSW_URLS.REST_CSW_OBJECT_LIST, {}]
            [ICSW_URLS.REST_QUOTA_CAPABLE_BLOCKDEVICE_LIST, {}]
            [ICSW_URLS.REST_VIRTUAL_DESKTOP_PROTOCOL_LIST, {}]
            [ICSW_URLS.REST_WINDOW_MANAGER_LIST, {}]
            [ICSW_URLS.REST_DEVICE_LIST, {}]
            [ICSW_URLS.REST_VIRTUAL_DESKTOP_USER_SETTING_LIST, {}]
        ])
        $scope.init_csw_cache = (entry, e_type) ->
            entry.permission = null
            entry.permission_level = 0
        $q.all(wait_list).then(
            (data) ->
                $scope.group_list = data[0]
                $scope.user_list = data[1]
                $scope.device_group_list = data[2]
                $scope.csw_permission_list = data[3]
                $scope.csw_permission_lut = {}
                for entry in $scope.csw_permission_list
                    $scope.csw_permission_lut[entry.idx] = entry
                    entry.model_name = entry.content_type.model
                #$scope.csw_object_permission_list = data[4]
                $scope.home_export_list = data[4]
                # beautify permission list
                for entry in $scope.csw_permission_list
                    info_str = "#{entry.name} (" + (if entry.valid_for_object_level then "G/O" else "G") + ")"
                    entry.info = info_str
                    if entry.valid_for_object_level
                        key = entry.content_type.app_label + "." + entry.content_type.model 
                        if key not of $scope.obj_perms
                            $scope.obj_perms[key] = []
                        $scope.obj_perms[key].push(entry)
                $scope.ct_dict = {}
                for entry in data[5]
                    $scope.ct_dict[entry.content_label] = entry.object_list
                $scope.group_edit.delete_list = $scope.group_list 
                $scope.group_edit.create_list = $scope.group_list
                $scope.user_edit.delete_list = $scope.user_list 
                $scope.user_edit.create_list = $scope.user_list
                $scope.qcb_list = data[6]
                $scope.qcb_lut = {}
                for entry in $scope.qcb_list
                    $scope.qcb_lut[entry.idx] = entry
                $scope.rebuild_tree()
                $scope.virtual_desktop_protocol = data[7]
                $scope.window_manager = data[8]
                $scope.device = data[9]
                $scope.virtual_desktop_user_setting = data[10]
                for vdus in $scope.virtual_desktop_user_setting
                    $scope.get_viewer_command_line(vdus)
        )
        $scope.sync_users = () ->
            blockUI.start("Sending sync to server ...")
            icswSimpleAjaxCall(
                url     : ICSW_URLS.USER_SYNC_USERS
                title   : "syncing users"
            ).then((xml) ->
            )
        $scope.rebuild_tree = () ->
            $scope.tree.clear_root_nodes()
            group_lut = {}
            rest_list = []
            for entry in $scope.group_list
                # set csw dummy permission list and optimizse object_permission list
                $scope.init_csw_cache(entry, "group")
                t_entry = $scope.tree.new_node(
                    folder: true
                    obj: entry
                    expand: !entry.parent_group
                    _node_type: "g"
                    always_folder: true
                )
                group_lut[entry.idx] = t_entry
                if entry.parent_group
                    # handle later
                    rest_list.push(t_entry)
                else
                    $scope.tree.add_root_node(t_entry)
            while rest_list.length > 0
                # iterate until the list is empty
                _rest_list = []
                for entry in rest_list
                    if entry.obj.parent_group of group_lut
                        group_lut[entry.obj.parent_group].add_child(entry)
                    else
                        _rest_list.push(entry)
                rest_list = _rest_list
            $scope.group_lut = group_lut
            $scope.parent_groups = {}
            for entry in $scope.group_list
                $scope.parent_groups[entry.idx] = $scope.get_parent_group_list(entry)
            for entry in $scope.user_list
                # set csw dummy permission list and optimise object_permission_list
                $scope.init_csw_cache(entry, "user")
                t_entry = $scope.tree.new_node({folder:false, obj:entry, _node_type:"u"})
                group_lut[entry.group].add_child(t_entry)
        $scope.$on("icsw.user.groupchange", () ->
            $scope.rebuild_tree()
        )
        $scope.$on("icsw.user.userchange", () ->
            $scope.rebuild_tree()
        )
        $scope.get_parent_group_list = (cur_group) ->
            _list = []
            for _group in $scope.group_list
                if _group.idx != cur_group.idx
                    add = true
                    # check if cur_group is not a parent
                    _cur_p = _group.parent_group
                    while _cur_p
                        _cur_p = $scope.group_lut[_cur_p].obj
                        if _cur_p.idx == cur_group.idx
                            add = false
                        _cur_p = _cur_p.parent_group
                    if add
                        _list.push(_group)
            return _list
        $scope.valid_device_groups = () ->
            _list = (entry for entry in $scope.device_group_list when entry.enabled == true and entry.cluster_device_group == false) 
            return _list
        $scope.valid_group_csw_perms = () ->
            _list = (entry for entry in $scope.csw_permission_list when entry.codename not in ["admin", "group_admin"]) 
            return _list
        $scope.valid_user_csw_perms = () ->
            return (entry for entry in $scope.csw_permission_list)
        $scope.object_list = () ->
            if $scope._edit_obj.permission
                perm = $scope.csw_permission_lut[$scope._edit_obj.permission]
                if perm.valid_for_object_level
                    key = "#{perm.content_type.app_label}.#{perm.content_type.model}"
                    if $scope.ct_dict[key] and $scope.ct_dict[key].length
                        if not $scope._edit_obj.object 
                            $scope._edit_obj.object = $scope.ct_dict[key][0].idx
                        return $scope.ct_dict[key]
            $scope._edit_obj.object = null
            return []
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
        $scope.update_filter = () ->
            if not $scope.filterstr
                cur_re = new RegExp("^$", "gi")
            else
                try
                    cur_re = new RegExp($scope.filterstr, "gi")
                catch exc
                    cur_re = new RegExp("^$", "gi")
            $scope.tree.iter(
                (entry, cur_re) ->
                    cmp_name = if entry._node_type == "g" then entry.obj.groupname else entry.obj.login
                    entry.set_selected(if cmp_name.match(cur_re) then true else false)
                cur_re
            )
            $scope.tree.show_selected(false)
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
            $scope.$digest()
        )
        $scope.change_password = () ->
            $scope.$broadcast("icsw.enter_password")
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
]).controller("icswUserAccountCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$timeout", "$modal", "ICSW_URLS", "icswUserService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $timeout, $modal, ICSW_URLS, icswUserService) ->
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
        $scope.change_password = () ->
            $scope.$broadcast("icsw.enter_password")
        $scope.get_vdus = (idx) ->
        $scope.update()
]).directive("icswUserGroupShow", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "A"
        template : $templateCache.get("group.detail.form")
        link : (scope, element, attrs) ->
            # not beautiful but working
            scope.$parent.form = scope.form
            scope.obj_perms = scope.$parent.obj_perms
    }
]).directive("icswUserUserShow", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "A"
        template : $templateCache.get("user.detail.form")
        link : (scope, element, attrs) ->
            # not beautiful but working
            scope.$parent.$parent.form = scope.form
            scope.obj_perms = scope.$parent.$parent.obj_perms
    }
]).directive("icswUserPermissions", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.permissions")
        link : (scope, element, attrs) ->
            scope.action = false
            scope.$watch(attrs["object"], (new_val) ->
                scope.object = new_val
                # user or group
                scope.type = attrs["type"]
            )
            scope.$watch(attrs["action"], (new_val) ->
                scope.action = new_val
            )
            scope.get_permission_set = () ->
                if scope.object?
                    if scope.type == "user"
                        return scope.object.user_permission_set
                    else
                        return scope.object.group_permission_set
                else
                    return []
            scope.get_object_permission_set = () ->
                if scope.object?
                    if scope.type == "user"
                        return scope.object.user_object_permission_set
                    else
                        return scope.object.group_object_permission_set
                else
                    return []
    }
]).directive("icswUserQuotaSettings", ["$compile", "$templateCache", "icswTools", ($compile, $templateCache, icswTools) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.quota.settings")
        link: (scope, element, attrs) ->
            scope.object = undefined
            scope.quota_settings = []
            scope.$watch(attrs["object"], (new_val) ->
                scope.object = new_val
                scope.type = attrs["type"]
                if scope.object?
                    # salt list
                    if scope.type == "user"
                        scope.quota_settings = scope.object.user_quota_setting_set
                    else
                        scope.quota_settings = scope.object.group_quota_setting_set
                    if scope.quota_settings
                        for entry in scope.quota_settings
                            entry.show_abs = false
                            # link
                            entry.qcb = scope.qcb_lut[entry.quota_capable_blockdevice]
                            entry.bytes_quota = if (entry.bytes_soft or entry.bytes_hard) then true else false
                            entry.files_quota = if (entry.files_soft or entry.files_hard) then true else false
                            # build stack
                            entry.files_stacked = scope.build_stacked(entry, "files", true)
                            entry.bytes_stacked_abs = scope.build_stacked(entry, "bytes", true)
                            entry.bytes_stacked_rel = scope.build_stacked(entry, "bytes", false)
            )
            scope.get_bytes_limit = (qs) ->
                if qs.bytes_soft or qs.bytes_hard
                    return icswTools.get_size_str(qs.bytes_soft, 1024, "B") + " / " + icswTools.get_size_str(qs.bytes_hard, 1024, "B")
                else
                    return "---"
            scope.get_files_limit = (qs) ->
                if qs.files_soft or qs.files_hard
                    return icswTools.get_size_str(qs.files_soft, 1000, "") + " / " + icswTools.get_size_str(qs.files_hard, 1000, "")
                else
                    return "---"
            scope.get_line_class = (qs) ->
                if (qs.bytes_hard and qs.bytes_used > qs.bytes_hard) or (qs.files_hard and qs.files_used > qs.files_hard)
                    _class = "danger"
                else if (qs.bytes_soft and qs.bytes_used > qs.bytes_soft) or (qs.files_soft and qs.files_used > qs.files_soft)
                    _class = "warning"
                else
                    _class = ""
                return _class
            scope.build_stacked = (qs, _type, abs) ->
                _used = qs["#{_type}_used"]
                _soft = qs["#{_type}_soft"]
                _hard = qs["#{_type}_hard"]
                r_stack = []
                if qs.qcb.size and (_soft or _hard)
                    if _type == "files"
                        _info1 = "files"
                        max_value = Math.max(_soft, _hard)
                        used_str = icswTools.get_size_str(_used, 1000, "")
                    else
                        _info1 = "space"
                        if abs
                            max_value = qs.qcb.size
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
]).directive("icswUserVirtualDesktopSettings", ["$compile", "$templateCache", "icswTools", "toaster", ($compile, $templateCache, icswTools, toaster) ->
        restrict : "EA"
        template : $templateCache.get("icsw.user.vdu.settings")
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
            scope.get_virtual_desktop_user_setting_of_user = (user_obj) ->
                return scope.virtual_desktop_user_setting.filter( (vdus) -> vdus.user == user_obj.idx && vdus.to_delete == false )
                
            scope.virtual_desktop_devices = () ->
                # devices which support both some kind of virtual desktop and window manager
                vd_devs = []
                for vd in scope.virtual_desktop_protocol
                    for dev_index in vd.devices
                        vd_devs.push(dev_index)
                        
                wm_devs = []
                for wm in scope.window_manager
                    for dev_index in wm.devices
                        wm_devs.push(dev_index)
                    
                # vd_devs and wm_devs contain duplicates, but we dont care
                inter = _.intersection(vd_devs, wm_devs)

                return (dev for dev in scope.device when not dev.is_meta_device and dev.idx in inter)
            scope.virtual_desktop_device_available = () ->
                return scope.virtual_desktop_devices().length > 0
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
            scope.get_device_by_index = (index) ->
                return _.find(scope.device, (vd) -> vd.idx == index)
            scope.get_virtual_desktop_protocol_by_index = (index) ->
                return _.find(scope.virtual_desktop_protocol, (vd) -> vd.idx == index)
            scope.get_window_manager_by_index = (index) ->
                return _.find(scope.window_manager, (vd) -> vd.idx == index)
            
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
                    "window_manager":   scope._edit_obj.window_manager
                    "virtual_desktop_protocol": scope._edit_obj.virtual_desktop_protocol 
                    "screen_size":      scope.get_selected_screen_size_as_string()
                    "device":           scope._edit_obj.device
                    "user":             scope._edit_obj.idx
                    "port":             scope._edit_obj.port
                    "websockify_port":             scope._edit_obj.websockify_port
                    "is_running":          scope._edit_obj.start_automatically
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
                scope._edit_obj.port = 0  # could perhaps depend on protocol
                scope._edit_obj.websockify_port = 0  # could perhaps depend on protocol
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
                vdus.put().then( () ->
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
                scope._edit_obj.screen_size = available_screen_sizes.filter( (x) -> x.name == vdus.screen_size )[0]

                scope._edit_obj.window_manager = vdus.window_manager
                scope._edit_obj.virtual_desktop_protocol = vdus.virtual_desktop_protocol

                scope._edit_obj.start_automatically = vdus.is_running
            
])

virtual_desktop_utils = {
    get_viewer_command_line: (vdus, ip) ->
        return "echo \"#{vdus.password}\" | vncviewer -autopass #{ip}:#{vdus.effective_port }\n"
}
