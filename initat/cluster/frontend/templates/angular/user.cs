{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

enter_password_template = """
<div class="modal-header"><h3>Please enter the new password</h3></div>
<div class="modal-body">
    <form name="form">
        <div ng-class="dyn_check(pwd.pwd1)">
            <label>Password:</label>
            <input type="password" ng-model="pwd.pwd1" placeholder="enter password" ng-trim="false" class="form-control"></input>
        </div>
        <div ng-class="dyn_check(pwd.pwd2)">
            <label>again:</label>
            <input type="password" ng-model="pwd.pwd2" placeholder="confirm password" ng-trim="false" class="form-control"></input>
        </div>
    </form>
</div>
<div class="modal-footer">
    <div ng-class="pwd_error_class">
       {% verbatim %}
           {{ pwd_error }}
       {% endverbatim %}
    </div>
    <div>
        <button class="btn btn-primary" ng-click="check()">Check</button>
        <button class="btn btn-success" ng-click="ok()" ng-show="check()">Save</button>
        <button class="btn btn-warning" ng-click="cancel()">Cancel</button>
    </div>
</div>
"""

{% verbatim %}

jobinfo_template = """
 <table class="table table-hover table-bordered table-condensed" style="width:100%;" >
    <thead>
        <tr>
            <th></th>
            <th>Number of jobs</th>
            <th>Job ids</th>
        </tr>
    </thead>

	<tbody>
	    <tr>
	        <td> Jobs waiting </td>
		    <td> {{ jobs_waiting.length }} </td>
		    <td> {{ longListToString(jobs_waiting) }} </td>
	    </tr>
	    <tr>
	        <td> Jobs running </td>
		    <td> {{ jobs_running.length }} </td>
		    <td> {{ longListToString(jobs_running) }} </td>
	    </tr>
	    <tr>
	        <td>
	            Jobs finished in 
	            <div class="btn-group">
		            <button type="button" class="btn btn-xs btn-primary dropdown-toggle" data-toggle="dropdown">
		                <span class="glyphicon glyphicon-dashboard"></span>
		                {{ last_jobinfo_timedelta.name }} <span class="caret"></span>
		            </button>
		            <ul class="dropdown-menu">
		                <li ng-repeat="ts in all_timedeltas" ng-click="set_jobinfo_timedelta(ts)"><a href="#">{{ ts.name }}</a></li>
		            </ul>
		         </div>
		    </td>
		    <td>{{ jobs_finished.length }}</td>
		    <td>{{ longListToString(jobs_finished) }}</td>
		</tr>
	</tbody>
</table>
"""

diskusage_template = """
<h4>{{ scan_run_info() }}<span ng-show="current_scan_run">, </span><input ng-show="current_scan_run" type="button" class="btn btn-xs" ng-class="show_dots && 'btn-success'" value="show dot dirs" ng-click="toggle_dots()"></input></h4>
<div ng-show="current_scan_run">
    <tree treeconfig="du_tree"></tree>
</div>
"""

quota_settings_template = """
<table class="table table-hover table-bordered table-condensed table-striped" style="width:100%;" ng-show="quota_settings.length">
    <thead>
        <tr>
            <th>Device</th>
            <th>Path</th>
            <th>Size</th>
            <th>Flags</th>
            <th>Bytes Graph</th>
            <th>Bytes used</th>
            <th>Bytes limit</th>
            <th>INode Graph</th>
            <th>INodes used</th>
            <th>INodes limit</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="qs in quota_settings" ng-class="get_line_class(qs)">
            <td>{{ qs.qcb.device.full_name }}</td>
            <td>{{ qs.qcb.mount_path }}</td>
            <td>{{ qs.qcb.size | get_size:1:1024 }}</td>
            <td class="center">{{ qs.quota_flags }}</td>
            <td style="width:200px;">
                <progress ng-show="qs.bytes_quota">
                    <bar ng-repeat="stack in qs.bytes_stacked track by $index" value="stack.value" title="{{ stack.title }}" type="{{ stack.type }}">{{ stack.out }}</bar>
                </progress>
            </td>
            <td class="text-center">{{ qs.bytes_used | get_size:1:1024 }}</td>
            <td class="text-center">{{ get_bytes_limit(qs) }}</td>
            <td style="width:120px;">
                <progress ng-show="qs.files_quota">
                    <bar ng-repeat="stack in qs.files_stacked track by $index" value="stack.value" title="{{ stack.title }}" type="{{ stack.type }}">{{ stack.out }}</bar>
                </progress>
            </td>
            <td class="text-center">{{ qs.files_used | get_size:1:1000:'' }}</td>
            <td class="text-center">{{ get_files_limit(qs) }}</td>
        </tr>
    </tbody>
</table>
<h4 ng-show="!quota_settings.length">no quota info</h4>
"""

permissions_template = """
<table class="table table-condensed table-hover table-striped" style="width:100%;">
    <thead>
        <tr>
            <th>Type</th>
            <th>Name</th>
            <th>Code</th>
            <th>Level</th>
            <th>Object</th>
            <th>Application</th>
            <th>Model</th>
            <th ng-show="action">Action</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="perm in get_permission_set()">
            <td>global</td>
            <td>{{ perm.csw_permission | array_lookup:csw_permission_list:'name' }}</td>
            <td>{{ perm.csw_permission | array_lookup:csw_permission_list:'codename' }}</td>
            <td>{{ get_perm_level(perm) }}</td>
            <td>&nbsp;</td>
            <td>{{ get_perm_app(perm) }}</td>
            <td>{{ get_perm_model(perm) }}</td>
            <td ng-show="action"><input type="button" class="btn btn-xs btn-danger" value="delete" ng-click="delete_permission(perm)"></input></td>
        </tr>
        <tr ng-repeat="perm in get_object_permission_set()">
            <td>local</td>
            <td>{{ perm.csw_object_permission.csw_permission | array_lookup:csw_permission_list:'name' }}</td>
            <td>{{ perm.csw_object_permission.csw_permission | array_lookup:csw_permission_list:'codename' }}</td>
            <td>{{ get_perm_level(perm) }}</td>
            <td>{{ get_perm_object(perm) }}</td>
            <td>{{ get_perm_app(perm.csw_object_permission) }}</td>
            <td>{{ get_perm_model(perm.csw_object_permission) }}</td>
            <td ng-show="action"><input type="button" class="btn btn-xs btn-danger" value="delete" ng-click="delete_object_permission(perm)"></input></td>
        </tr>
    </tbody>
</table>
"""

{% endverbatim %}

angular_add_password_controller = (module, name) ->
    module.run(($templateCache) ->
        $templateCache.put("set_password.html", enter_password_template)
    )
    module.controller("password_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
        ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal) ->
            $scope.$on("icsw.enter_password", () ->
                $modal.open
                    template : $templateCache.get("set_password.html")
                    controller : ($scope, $modalInstance, scope) ->
                        $scope.pwd = {
                            "pwd1" : ""
                            "pwd2" : ""
                        }
                        $scope.dyn_check = (val) ->
                            $scope.check()
                            _rc = []
                            if val.length < 8
                                _rc.push("has-error")
                            return _rc.join(" ")
                        $scope.ok = () ->
                            $modalInstance.close(true)
                            scope.$emit("icsw.set_password", $scope.pwd.pwd1)
                        $scope.check = () ->
                            if $scope.pwd.pwd1 == "" and $scope.pwd.pwd1 == $scope.pwd.pwd2
                                $scope.pwd_error = "empty passwords"
                                $scope.pwd_error_class = "alert alert-warning"
                                return false
                            else if $scope.pwd.pwd1.length >= 8 and $scope.pwd.pwd1 == $scope.pwd.pwd2
                                $scope.pwd_error = "passwords match"
                                $scope.pwd_error_class = "alert alert-success"
                                return true
                            else
                                $scope.pwd_error = "passwords do not match or too short"
                                $scope.pwd_error_class = "alert alert-danger"
                                return false
                        $scope.cancel = () ->
                            $modalInstance.dismiss("cancel")
                    backdrop : "static"
                    resolve:
                        scope: () ->
                            return $scope
            )
    ])

password_test_module = angular.module("icsw.password.test", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"])

angular_module_setup([password_test_module])

angular_add_password_controller(password_test_module)

user_module = angular.module("icsw.user", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "noVNC", "ui.select"])

angular_module_setup([user_module])

add_tree_directive(user_module)

angular_add_password_controller(user_module)

DT_FORM = "YYYY-MM-DD HH:mm"

class user_tree extends tree_config
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


class diskusage_tree extends tree_config
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

        
user_module.controller("user_tree", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal) ->
        $scope.ac_levels = [
            {"level" : 0, "info" : "Read-only"},
            {"level" : 1, "info" : "Modify"},
            {"level" : 3, "info" : "Modify, Create"},
            {"level" : 7, "info" : "Modify, Create, Delete"},
        ]
        $scope.obj_perms = {}
        $scope.tree = new user_tree($scope)
        $scope.filterstr = ""
        # init edit mixins
        $scope.group_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular)
        $scope.group_edit.modify_rest_url = "{% url 'rest:group_detail' 1 %}".slice(1).slice(0, -2)
        $scope.group_edit.create_rest_url = Restangular.all("{% url 'rest:group_list' %}".slice(1))
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
        $scope.user_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular)
        $scope.user_edit.modify_rest_url = "{% url 'rest:user_detail' 1 %}".slice(1).slice(0, -2)
        $scope.user_edit.create_rest_url = Restangular.all("{% url 'rest:user_list' %}".slice(1))
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
            ["{% url 'rest:group_list' %}", {}]
            ["{% url 'rest:user_list' %}", {}]
            ["{% url 'rest:device_group_list' %}", {}]
            ["{% url 'rest:csw_permission_list' %}", {}]
            ["{% url 'rest:home_export_list' %}", {}]
            ["{% url 'rest:csw_object_list' %}", {}]
            ["{% url 'rest:quota_capable_blockdevice_list' %}", {}]
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
                    #info_str = entry.content_type.app_label + " | " + entry.content_type.name + " | " + entry.name + " | " + (if entry.valid_for_object_level then "G/O" else "G")
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
        )
        $scope.sync_users = () ->
            $.blockUI()
            call_ajax
                url     : "{% url 'user:sync_users' %}"
                title   : "syncing users"
                success : (xml) =>
                    $.unblockUI()
                    parse_xml_response(xml)
        $scope.rebuild_tree = () ->
            $scope.tree.clear_root_nodes()
            group_lut = {}
            rest_list = []
            for entry in $scope.group_list
                # set csw dummy permission list and optimizse object_permission list
                $scope.init_csw_cache(entry, "group")
                t_entry = $scope.tree.new_node({folder:true, obj:entry, expand:!entry.parent_group, _node_type:"g"})
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
        )
        $scope.change_password = () ->
            $scope.$broadcast("icsw.enter_password")
        $scope.create_object_permission = () ->
            perm = $scope.csw_permission_lut[$scope._edit_obj.permission]
            call_ajax
                url     : "{% url 'user:change_object_permission' %}"
                data    :
                    # group or user
                    "auth_type" : $scope._edit_mode
                    "auth_pk"   : $scope._edit_obj.idx
                    "model_label" : perm.content_type.model
                    "obj_idx" : $scope._edit_obj.object
                    "csw_idx" : $scope._edit_obj.permission
                    "set"     : 1
                    "level"   : $scope._edit_obj.permission_level
                success : (xml) =>
                    if parse_xml_response(xml)
                        if $(xml).find("value[name='new_obj']").length
                            new_obj = angular.fromJson($(xml).find("value[name='new_obj']").text())
                            if $scope._edit_mode == "u"
                                $scope._edit_obj.user_object_permission_set.push(new_obj)
                            else
                                $scope._edit_obj.group_object_permission_set.push(new_obj)
                            noty
                                text : "added local permission"
                            # trigger redraw
                            $scope.$digest()
        $scope.delete_permission = (perm) ->
            if $scope._edit_mode == "u"
                ug_name = "user"
                detail_url = "{% url 'rest:user_permission_detail' 1 %}".slice(1).slice(0, -2)
            else
                ug_name = "group"
                detail_url = "{% url 'rest:group_permission_detail' 1 %}".slice(1).slice(0, -2)
            ps_name = "#{ug_name}_permission_set"
            Restangular.restangularizeElement(null, perm, detail_url)
            perm.remove().then((data) ->
                $scope._edit_obj[ps_name] = (_e for _e in $scope._edit_obj[ps_name] when _e.csw_permission != perm.csw_permission)
                noty
                    text : "removed global #{ug_name} permission"
                    type : "warning"
            )
        $scope.delete_object_permission = (perm) ->
            if $scope._edit_mode == "u"
                ug_name = "user"
                detail_url = "{% url 'rest:user_object_permission_detail' 1 %}".slice(1).slice(0, -2)
            else
                ug_name = "group"
                detail_url = "{% url 'rest:group_object_permission_detail' 1 %}".slice(1).slice(0, -2)
            ps_name = "#{ug_name}_object_permission_set"
            Restangular.restangularizeElement(null, perm, detail_url)
            perm.remove().then((data) ->
                $scope._edit_obj[ps_name] = (_e for _e in $scope._edit_obj[ps_name] when _e.idx != perm.idx)
                noty
                    text : "removed local #{ug_name} permission"
                    type : "warning"
            )
        $scope.create_permission = () ->
            if $scope._edit_obj.permission
                if $scope._edit_mode == "u"
                    ug_name = "user"
                    list_url = "{% url 'rest:user_permission_list' %}".slice(1)
                else
                    ug_name = "group"
                    list_url = "{% url 'rest:group_permission_list' %}".slice(1)
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
            call_ajax
                url     : "{% url 'user:clear_home_dir_created' %}"
                data    :
                    "user_pk" : obj.idx
                success : (xml) =>
                    if parse_xml_response(xml)
                        $scope.$apply(() ->
                            obj.home_dir_created = false
                        )
        $scope.get_perm_object = (perm) ->
            obj_perm = perm.csw_object_permission
            csw_perm = $scope.csw_permission_lut[obj_perm.csw_permission]
            key = "#{csw_perm.content_type.app_label}.#{csw_perm.content_type.model}"
            return (_v.name for _v in $scope.ct_dict[key] when _v.idx == obj_perm.object_pk)[0]
                
]).controller("account_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal) ->
        $scope.ac_levels = [
            {"level" : 0, "info" : "Read-only"},
            {"level" : 1, "info" : "Modify"},
            {"level" : 3, "info" : "Modify, Create"},
            {"level" : 7, "info" : "Modify, Create, Delete"},
        ]
        $scope.update = () ->
            wait_list = restDataSource.add_sources([
                ["{% url 'rest:csw_permission_list' %}", {}]
                ["{% url 'rest:csw_object_list' %}", {}]
                ["{% url 'rest:quota_capable_blockdevice_list' %}", {}]
            ])
            wait_list.push(Restangular.one("{% url 'rest:user_detail' 1 %}".slice(1).slice(0, -2), {{ user.pk }}).get())
            $q.all(wait_list).then(
                (data) ->
                    # update once per minute
                    $timeout($scope.update, 60000)
                    $scope.edit_obj = data[3]
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
            )
        $scope.update_account = () ->
            $scope.edit_obj.put().then(
               (data) ->
               (resp) ->
            )
        $scope.$on("icsw.set_password", (event, new_pwd) ->
            $scope.edit_obj.password = new_pwd
            $scope.update_account()
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
        $scope.update()
]).controller("jobinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal)->
        $scope.jobs_waiting = []
        $scope.jobs_running = []
        $scope.jobs_finished = []
        class jobinfo_timedelta
            constructor: (@name, @timedelta_description) ->
        $scope.all_timedeltas = [
            new jobinfo_timedelta("last 15 minutes", [15, "minutes"])
            new jobinfo_timedelta("last hour", [1, "hours"])
            new jobinfo_timedelta("last 4 hours", [4, "hours"])
            new jobinfo_timedelta("last day", [1, "days"])
            new jobinfo_timedelta("last week", [1, "weeks"])
        ]
        $scope.set_jobinfo_timedelta = (ts) ->
            $scope.last_jobinfo_timedelta = ts
            jobsfrom = moment().subtract(
                ts.timedelta_description[0],
                ts.timedelta_description[1]
            ).unix()
            call_ajax
                  url      : "{% url 'rms:get_rms_jobinfo' %}"
                  data     :
                      "jobinfo_jobsfrom" : jobsfrom
                  dataType : "json"
                  success  : (json) =>
                      $scope.$apply(
                          $scope.jobs_running = json.jobs_running
                          $scope.jobs_waiting = json.jobs_waiting
                          $scope.jobs_finished = json.jobs_finished
                      )
        $scope.set_jobinfo_timedelta( $scope.all_timedeltas[1] )
        listmax = 15
        jobidToString = (j) -> 
            if j[1] != ""
                return " "+j[0]+":"+j[1]
            else
                return " "+j[0]
                    
        $scope.longListToString = (l) ->
            if l.length < listmax
                return [jobidToString(i) for i in l].toString()
            else
                return (jobidToString(i) for i in l[0..listmax]).toString() + ", ..."
]).directive("grouptemplate", ($compile, $templateCache) ->
    return {
        restrict : "A"
        template : $templateCache.get("group_edit.html")
        link : (scope, element, attrs) ->
            # not beautiful but working
            scope.$parent.form = scope.form
            scope.obj_perms = scope.$parent.obj_perms
    }
).directive("usertemplate", ($compile, $templateCache) ->
    return {
        restrict : "A"
        template : $templateCache.get("user_edit.html")
        link : (scope, element, attrs) ->
            # not beautiful but working
            scope.$parent.$parent.form = scope.form
            scope.obj_perms = scope.$parent.$parent.obj_perms
    }
).directive("permissions", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("permissions.html")
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
).directive("quotasettings", ($compile, $templateCache, icswTools) ->
    return {
        restrict : "EA"
        template : $templateCache.get("quotasettings.html")
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
                            # link
                            entry.qcb = scope.qcb_lut[entry.quota_capable_blockdevice]
                            entry.bytes_quota = if (entry.bytes_soft or entry.bytes_hard) then true else false
                            entry.files_quota = if (entry.files_soft or entry.files_hard) then true else false
                            # build stack
                            entry.files_stacked = scope.build_stacked(entry, "files")
                            entry.bytes_stacked = scope.build_stacked(entry, "bytes")
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
            scope.build_stacked = (qs, _type) ->
                _used = qs["#{_type}_used"]
                _soft = qs["#{_type}_soft"]
                _hard = qs["#{_type}_hard"]
                r_stack = []
                if qs.qcb.size and (_soft or _hard)
                    if _type == "files"
                        _info1 = "files"
                        max_value = Math.max(_soft, _hard)
                    else
                        _info1 = "space"
                        max_value = qs.qcb.size    
                    _filled = parseInt(100 * _used / max_value)
                    r_stack.push(
                        {
                            "value" : _filled
                            "type" : "success"
                            "out" : "#{_filled}%"
                            "title" : "#{_info1} used"
                        }
                    )
                    if _used < _soft
                        # soft limit not reached
                        _lsoft = parseInt(100 * (_soft - _used) / max_value)
                        r_stack.push(
                            {
                                "value" : _lsoft
                                "type" : "warning"
                                "out": "#{_lsoft}%"
                                "title" : "#{_info1} left until soft limit is reached"
                            }
                        )
                        if _hard > _soft
                            _sth = parseInt(100 * (_hard - _soft) / max_value)
                            r_stack.push(
                                {
                                    "value" : _sth
                                    "type" : "info"
                                    "out": "#{_sth}%"
                                    "title" : "difference from soft to hard limit"
                                }
                            )
                    else
                        # soft limit reached
                        _lhard = parseInt(100 * (_hard - _used) / max_value)
                        r_stack.push(
                            {
                                "value" : _lhard
                                "type" : if _soft then "danger" else "warning"
                                "out": "#{_lhard}%"
                                "title" : "#{_info1} left until hard limit is reached"
                            }
                        )
                return r_stack
    }
).directive("diskusage", ($compile, $templateCache, icswTools) ->
    return {
        restrict : "EA"
        template : $templateCache.get("diskusage.html")
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
                    # salt list
                    if scope.type == "user"
                        scope.scan_runs = scope.object.user_scan_run_set
                        _valid = (_entry for _entry in scope.scan_runs when _entry.current = true)
                        if _valid.length
                            scope.current_scan_run = _valid[0]
                            scope.build_tree()
                            # build tree
                        else
                            scope.current_scan_run = null
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
                scope.du_tree = new diskusage_tree(scope)
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
                    t_entry = scope.du_tree.new_node({folder:false, obj:entry, expand:entry.full_name in _expanded, always_folder:true})
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
).directive("jobinfo", ($compile, $templateCache, icswTools) ->
        restrict : "EA"
        template : $templateCache.get("jobinfo.html")
        link: (scope, element, attrs) ->
        	scope.get_jobs_done = () -> 42
        	scope.jobs_done = 44
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("quotasettings.html", quota_settings_template)
    $templateCache.put("permissions.html", permissions_template)
    $templateCache.put("jobinfo.html", jobinfo_template)
    $templateCache.put("diskusage.html", diskusage_template)
).controller("index_base", ["$scope", "$timeout", "$window",
    ($scope, $timeout, $window) ->
        $scope.show_index = true
        $scope.quick_open = true
        $scope.ext_open = false
        $scope.diskusage_open = true
        $scope.vdesktop_open = false
        $scope.jobinfo_open = true
        $scope.CLUSTER_LICENSE = $window.CLUSTER_LICENSE
        $scope.GLOBAL_PERMISSIONS = $window.GLOBAL_PERMISSIONS
        $scope.OBJECT_PERMISSIONS = $window.OBJECT_PERMISSIONS
        $scope.NUM_QUOTA_SERVERS = $window.NUM_QUOTA_SERVERS
        $scope.check_perm = (p_name) ->
            if p_name of GLOBAL_PERMISSIONS
                return true
            else if p_name of OBJECT_PERMISSIONS
                return true
            else
                return false
        $scope.set_visibility = (flag) ->
            $scope.show_index = flag
])

root.angular_add_password_controller = angular_add_password_controller

{% endinlinecoffeescript %}

</script>
