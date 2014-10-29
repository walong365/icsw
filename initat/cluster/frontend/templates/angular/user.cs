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

vncwebviewer_template = """
<!-- vnc viewer mode -->
<div ng-if="show_single_vdus && ips_loaded">
    <vnc host="{{ ips_for_devices[single_vdus.device] }}" port="{{ single_vdus.websockify_effective_port  }}" is-connected="show_single_vdus" password="{{ single_vdus.password }}" ></vnc>
</div>
<!-- dashboard mode -->
<div ng-if="virtual_desktop_sessions.length == 0">
    No virtual desktop sessions 
</div>
<table ng-if="(!show_single_vdus) && ips_loaded">
    <tr ng-repeat="vdus in virtual_desktop_sessions">
        <td>
            <table>
                <tr>
                    <td colspan="2">
                        <h4 class="ng-binding">
                            {{ get_virtual_desktop_protocol(vdus.virtual_desktop_protocol).description }} session on {{ get_device_by_index(vdus.device).name }} ({{ips_for_devices[vdus.device]}}:{{vdus.effective_port }}) running {{ get_window_manager(vdus.window_manager).description }}
                        </h4>
                   </td>
                </tr>
                <tr>
                    <td>
                        <button type="button" ng-click="show_viewer_command_line(vdus)" class="btn btn-default">Show viewer command line</button>
                        <br />
                        <p>
                            {{vdus.viewer_cmd_line}}
                        </p>
                    </td>
                    <td>
                          <button type="button" ng-click="open_vdus_in_new_tab(vdus)" class="btn btn-default">open in new tab</button>
                    </td>
                </tr>
                <tr>
                    <td colspan="2">

                        <accordion close-others="false">
                           <accordion-group is-open="web_viewer">
                               <accordion-heading>
                                   Web viewer
                                   <i class="pull-right glyphicon" ng-class="{'glyphicon-chevron-down': web_viewer, 'glyphicon-chevron-right': !web_viewer}"></i>
                               </accordion-heading>
                               <vnc host="{{ ips_for_devices[vdus.device] }}" port="{{ vdus.websockify_effective_port  }}" is-connected="true" password="{{ vdus.password }}" display="{width:1024,height:768,fitTo:'width',}"></vnc>
                           </accordion-group>
                           </accordion>
      
                    </td>
                </tr>
            </table
      </td>
    </tr>
</table>
"""		
virtual_desktop_settings_template = """
<fieldset  ng-show="true">
    <legend>Virtual Desktops</legend>
    <div ng-show="!virtual_desktop_device_available()">
        <p>No device supporting a virtual desktop protocol and a window manager found</p>
    </div>
    <div id="div_id_device" class="form-group" ng_show="virtual_desktop_device_available()">
        <label for="id_device" class="control-label col-sm-2">
           Device
        </label>
        <div class="controls col-sm-8">
            <div class='input-group' style='max-width:400px; min-width:240px;'>
            <ui-select ng-model='_edit_obj.device' ng-disabled='false' ng-change="on_device_change()">
                <ui-select-match placeholder='Select a device'>{{$select.selected.name}}</ui-select-match>
                <ui-select-choices repeat='value.idx as value in virtual_desktop_devices()' group-by='&#39;model_name&#39;'>
                    <div ng-bind-html='value.name | highlight: $select.search'></div>
                </ui-select-choices>
            </ui-select>
            <span class='input-group-btn'>
            <button type="button" ng-click="_edit_obj.device = undefined" class="btn btn-default"><span class="glyphicon glyphicon-trash"></span></button> </span></div>
        </div>
    </div>
            
   <div id="div_id_virtual_desktop_protocol" class="form-group " ng_show="_edit_obj.device" >
       <label for="id_virtual_desktop_protocol" class="control-label col-sm-2">
           Virtual desktop protocol
       </label>
       <div class="controls col-sm-8"><ui-select  ng-model='_edit_obj.virtual_desktop_protocol' style='max-width:400px; min-width:240px;' ng-disabled='false'><ui-select-match placeholder='Select an virtual desktop protocol'>{{$select.selected.description}}</ui-select-match><ui-select-choices repeat='value.idx as value in get_available_virtual_desktop_protocols(_edit_obj.device)' group-by='&#39;model_name&#39;'><div ng-bind-html='value.description | highlight: $select.search'></div></ui-select-choices></ui-select></div>
   </div>

   <div id="div_id_port" class="form-group " ng_show="_edit_obj.device" >
       <label for="id_port" class="control-label col-sm-2">
           Port
       </label>
       <div class="controls col-sm-8">
           <input class="numberinput form-control" id="id_port" max="65535" min="0" name="port" ng-model="_edit_obj.port" placeholder="0" type="number" /> 
       </div>
   </div>

   <div id="div_id_web_vnc_port" class="form-group " ng_show="_edit_obj.device" >
       <label for="id_web_vnc_port" class="control-label col-sm-2">
           Web VNC Port
       </label>
       <div class="controls col-sm-8">
           <input class="numberinput form-control" id="id_web_vnc_port" max="65535" min="0" name="port" ng-model="_edit_obj.websockify_port" placeholder="0" type="number" /> 
       </div>
   </div>
   
   <div id="div_id_window_manager" class="form-group " ng_show="_edit_obj.device" ><label for="id_window_manager" class="control-label col-sm-2">
           Window manager
       </label>
       <div class="controls col-sm-8">
           <ui-select ng-model='_edit_obj.window_manager' style='max-width:400px; min-width:240px;' ng-disabled='false'>
               <ui-select-match placeholder='Select a wm'>{{$select.selected.description}}</ui-select-match>
               <ui-select-choices repeat='value.idx as value in get_available_window_managers(_edit_obj.device)' group-by='&#39;model_name&#39;'>
                   <div ng-bind-html='value.description | highlight: $select.search'></div>
               </ui-select-choices>
           </ui-select>
       </div>
  </div>

  <div id="div_id_screen_size" class="form-group " ng_show="_edit_obj.device" >
       <label for="id_screen_size" class="control-label col-sm-2">
           Screen size
       </label>
       <div class="controls col-sm-8"><ui-select  ng-model='_edit_obj.screen_size' style='max-width:400px; min-width:240px;' ng-disabled='false'><ui-select-match placeholder='...'>{{$select.selected.name}}</ui-select-match><ui-select-choices repeat='value as value in available_screen_sizes'><div ng-bind-html='value.name | highlight: $select.search'></div></ui-select-choices></ui-select></div>
   </div>

  
  <div>
      <div class="control-label col-sm-2" > &nbsp; </div>
      <div class="controls form-inline" ng_show="_edit_obj.device && _edit_obj.screen_size.manual">
              <input class="numberinput form-control" type="number" min="200", max="6000" ng-model="_edit_obj.manual_screen_size_x"></input> x <input class="numberinput form-control" type="number" min="200", max="6000" ng-model="_edit_obj.manual_screen_size_y"></input>
      </div>
  </div>
  
  <div  ng-show="_edit_obj.device">
      <!--<div  class="control-label col-sm-2" > &nbsp; </div>-->
  <div class="form-group">
      <div id="div_id_start_automatically" class="checkbox " >
          <div class="controls col-lg-offset-0 col-sm-8">
              <label for="id_start_automatically" class="">
              <input class="checkboxinput checkbox" id="id_start_automatically" name="start_automatically" ng-model="_edit_obj.start_automatically" type="checkbox" />
          Running (Check to make sure the server is always running)</label></div></div></div>
  </div>
               
               
  <input type="button" name="" value="{{ get_virtual_desktop_submit_mode() }}" class="btn btn btn-sm btn-success" id="button-id-" ng-click="create_virtual_desktop_user_setting()" ng-show="_edit_obj.device" />
  <input type="button" name="" value="cancel" class="btn btn btn-sm btn-danger" id="button-id-" ng-click="cancel_virtual_desktop_user_setting()" ng-show="_edit_obj.device" />
</fieldset>

<table class="table table-condensed table-hover table-striped" style="width:100%;">
    <thead>
        <tr>
            <th>Device</th>
            <th>Protocol</th>
            <th>Port</th>
            <th>Web VNC Port</th>
            <th>Window<br/>manager</th>
            <th>Screen size</th>
            <th>Running</th>
            <th>Action</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="vdus in get_virtual_desktop_user_setting_of_user(_edit_obj)">
            <td> {{ get_device_by_index(vdus.device).name }} </td>
            <td> {{ get_virtual_desktop_protocol_by_index(vdus.virtual_desktop_protocol).description }} </td>
            <td> {{ vdus.port }} </td>
            <td> {{ vdus.websockify_port }} </td>
            <td> {{ get_window_manager_by_index(vdus.window_manager).description }} </td>
            <td> {{ vdus.screen_size }} </td>
            <td> {{ vdus.is_running | yesno2 }} </td>
            <td>
                <input type="button" class="btn btn-xs btn-success" value="modify" ng-click="modify_virtual_desktop_user_setting(vdus)"></input>
                <input type="button" class="btn btn-xs btn-danger" value="delete" ng-click="delete_virtual_desktop_user_setting(vdus)"></input>
            </td>
        </tr>
    </tbody>
</table>
"""

jobinfo_template = """
<table class="table table-hover table-bordered table-condensed" style="width:100%;" ng-show="jobinfo_valid">
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
<h4 ng-show="!jobinfo_valid">waiting for jobinfo ...</h4>
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

class sidebar_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
    handle_click: (entry, event) =>
        if entry._node_type == "d"
            dev = @scope.dev_lut[entry.obj]
            if dev.device_type_identifier != "MDX"
                # create modal or use main view
                if @scope.index_view
                    # replace index
                    show_device_on_index([dev.idx])
                else
                    # modal
                    new device_info(event, dev.idx).show()
    get_name: (t_entry) ->
        entry = @get_dev_entry(t_entry)
        if t_entry._node_type == "f"
            if entry.parent
                return "#{entry.name} (*.#{entry.full_name})"
            else
                return "[TLN]"
        else if t_entry._node_type == "c"
            return if entry.depth then entry.name else "[TOP]"
        else
            info_f = []
            if entry.is_meta_device
                d_name = entry.full_name.slice(8)
            else
                d_name = entry.full_name
                info_f.push(entry.device_type_identifier)
            if entry.comment
                info_f.push(entry.comment)
            if info_f.length
                d_name = "#{d_name} (" + info_f.join(", ") + ")"
            return d_name
    get_icon_class: (t_entry) =>
        if t_entry._node_type == "d"
            entry = @get_dev_entry(t_entry)
            if entry.is_meta_device
                if entry.has_active_rrds
                    return "glyphicon glyphicon-pencil"
                else
                    return "dynatree-icon"
            else
                if entry.has_active_rrds
                    return "glyphicon glyphicon-pencil"
                else
                    return ""
        else
            return "dynatree-icon"
    get_dev_entry: (t_entry) =>
        if t_entry._node_type == "f"
            return @scope.fqdn_lut[t_entry.obj]
        else if t_entry._node_type == "c"
            return @scope.cat_lut[t_entry.obj]
        else
            return @scope.dev_lut[t_entry.obj]
    selection_changed: () =>
        @scope.selection_changed()
        
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
        
user_module.factory("icsw_devsel", ["$rootScope", ($rootScope) ->
    devs = {}
    selection = {
        "dev_pk_list": []
        "dev_pk_nmd_list": []
        "devg_pk_list": []
        "dev_pk_md_list": []
        "clients": 0
    }
    console.log "init", $rootScope
    register_client = () ->
        selection.clients++
        console.log "++"
        signal()
    signal = () ->
        console.log "signal", $rootScope
        $rootScope.$broadcast("icsw_devsel_changed")
    register_handler = (scope, handler) ->
        console.log "reg", scope, handler
        scope.$on("icsw_devsel_changed", () ->
            console.log "****"
            handler()
        )
    return {
         "selection": selection
         "register_client": register_client
         "register_handler": register_handler
    }
]).controller("user_tree", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal",
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
            ["{% url 'rest:virtual_desktop_protocol_list' %}", {}]
            ["{% url 'rest:window_manager_list' %}", {}]
            ["{% url 'rest:device_list' %}", {}]
            ["{% url 'rest:virtual_desktop_user_setting_list' %}", {}]
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
                $scope.virtual_desktop_protocol = data[7]
                $scope.window_manager = data[8]
                $scope.device = data[9]
                $scope.virtual_desktop_user_setting = data[10]
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

        $scope.push_virtual_desktop_user_setting = (new_obj, then_fun) ->
            url = "{% url 'rest:virtual_desktop_user_setting_list' %}".slice(1)
            Restangular.all(url).post(new_obj).then( then_fun )

                
]).controller("account_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal) ->
        $scope.virtual_desktop_user_setting = []
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
                ["{% url 'rest:virtual_desktop_user_setting_list' %}", {}]
                ["{% url 'rest:virtual_desktop_protocol_list' %}", {}]
                ["{% url 'rest:window_manager_list' %}", {}]
                ["{% url 'rest:device_list' %}", {}]
            ])
            wait_list.push(Restangular.one("{% url 'rest:user_detail' 1 %}".slice(1).slice(0, -2), {{ user.pk }}).get())
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
        $scope.get_vdus = (idx) ->
            $scope.virtual_desktop_user_setting.filter((vdus) ->  vdus.idx == idx)
        $scope.update()
]).controller("jobinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal)->
        $scope.jobs_waiting = []
        $scope.jobs_running = []
        $scope.jobs_finished = []
        $scope.jobinfo_valid = false
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
                          $scope.jobinfo_valid = true
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
).directive("virtualdesktopsettings", ($compile, $templateCache, icswTools) ->
        restrict : "EA"
        template : $templateCache.get("virtualdesktopsettings.html")
        link: (scope, element, attrs) ->
            scope.available_screen_sizes = available_screen_sizes
            scope.current_vdus = null
            scope.get_virtual_desktop_submit_mode = () ->
                if scope.current_vdus == null
                    return "create"
                else
                    return"modify"
            scope.cancel_virtual_desktop_user_setting = () ->
                scope.$apply(
                        scope._edit_obj.device = undefined
                )
                scope.current_vdus = null
            scope.get_virtual_desktop_user_setting_of_user = (user_obj) ->
                return scope.virtual_desktop_user_setting.filter( (vdus) -> vdus.user == user_obj.idx )
                
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
                        noty
                            text : "added virtual desktop setting"
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
                vdus.remove().then( () ->
                    # also remove locally
                    index = scope.virtual_desktop_user_setting.indexOf(vdus)
                    scope.virtual_desktop_user_setting.splice(index, 1)
                    noty
                        text : "removed virtual desktop setting"
                        type : "warning"
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
).directive("vncwebviewer", ($compile, $templateCache, icswTools) ->
        restrict : "EA"
        template : $templateCache.get("vncwebviewer.html")
        link: (scope, element, attrs) ->
            scope.object = undefined
            
            scope.ips_for_devices = {}
            scope.ips_loaded = false

            scope.single_vdus_index = {{ vdus_index }} # from django via get parameter
            scope.single_vdus = undefined
            scope.show_single_vdus = false

            scope.virtual_desktop_sessions = []
            scope.virtual_desktop_user_setting = []
            scope.$watch(attrs["object"], (new_val) ->
                scope.object = new_val
                    
                if scope.object?
                    scope.virtual_desktop_sessions = scope.virtual_desktop_user_setting.filter((vdus) ->  vdus.user == scope.object.idx)
                    # get all ips
                    scope.retrieve_device_ip vdus.device for vdus in scope.virtual_desktop_sessions

                    if scope.single_vdus_index
                        scope.single_vdus = scope.virtual_desktop_user_setting.filter((vdus) -> vdus.idx == scope.single_vdus_index)[0]
                        scope.show_single_vdus = true
            )
            scope.get_vnc_display_attribute_value = (geometry) ->
                [w, h] = screen_size.parse_screen_size(geometry)
                return "{width:"+w+",height:"+h+",fitTo:'width',}"
            scope.get_device_by_index = (index) ->
                return _.find(scope.device, (vd) -> vd.idx == index)
            scope.get_virtual_desktop_protocol = (index) ->
                return _.find(scope.virtual_desktop_protocol, (vd) -> vd.idx == index)
            scope.get_window_manager = (index) ->
                return _.find(scope.window_manager, (vd) -> vd.idx == index)
            scope.open_vdus_in_new_tab = (vdus) ->
                url = "{% url 'main:virtual_desktop_viewer' %}"
                window.open(url + "?vdus_index="+vdus.idx)
            scope.show_viewer_command_line = (vdus) ->
                vdus.viewer_cmd_line = "echo \"#{vdus.password}\" | vncviewer -autopass #{scope.ips_for_devices[vdus.device] }:#{vdus.effective_port }\n"
            scope.retrieve_device_ip = (index) ->
                # set some dummy value so that the vnc directive doesn't complain
                dummy_ip = "0.0.0.0"
                scope.ips_for_devices[index] = dummy_ip
                call_ajax
                    url      : "{% url 'user:get_device_ip' %}"
                    data     :
                        "device" : index
                    dataType : "json"
                    success  : (json) =>
                        console.log("answer:")
                        console.log(json)
                        scope.$apply(
                            scope.ips_for_devices[index] = json.ip
                            if _.indexOf(scope.ips_for_devices, dummy_ip) == -1
                                # all are loaded
                                scope.ips_loaded = true
                        )
                
            scope.download_vdus_start_script = (vdus) ->
                # currently unused
                script = "#!/bin/sh\n"+
                         "echo \"#{vdus.password}\" | vncviewer -autopass #{scope.get_device_by_index(vdus.device).name }:#{vdus.effective_port }\n"
                blob = new Blob([ script ], { type : 'text/x-shellscript' });
                url = (window.URL || window.webkitURL).createObjectURL( blob );
                hidden = document.createElement('a')
                hidden.href = url
                hidden.target = "_blank"
                hidden.download = "start_virtual_desktop_viewer.sh"
                hidden.click()
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("quotasettings.html", quota_settings_template)
    $templateCache.put("virtualdesktopsettings.html", virtual_desktop_settings_template)
    $templateCache.put("permissions.html", permissions_template)
    $templateCache.put("jobinfo.html", jobinfo_template)
    $templateCache.put("diskusage.html", diskusage_template)
    $templateCache.put("vncwebviewer.html", vncwebviewer_template)
).controller("index_base", ["$scope", "$timeout", "$window",
    ($scope, $timeout, $window) ->
        $scope.show_index = true
        $scope.quick_open = true
        $scope.ext_open = false
        $scope.diskusage_open = true
        $scope.vdesktop_open = true
        $scope.jobinfo_open = true
        $scope.show_devices = false
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
            $scope.$apply(
                $scope.show_index = flag
            )
        $scope.use_devs = (dev_list, devg_list, md_list) ->
            if dev_list.length
                # only use when at least one device is selected
                cur_di = new device_info(
                    undefined,
                    dev_list[0],
                    (entry for entry in dev_list[1..]),
                    md_list,
                    $("div#center_deviceinfo").attr("mode")
                )
                $scope.set_index_visibility(false)
                $scope.show_devices = true
                $("div#center_deviceinfo").show()
                cur_di.show()
            else
                # check for active device_info
                if window.ICSW_DEV_INFO?
                    window.ICSW_DEV_INFO.close()
                $scope.show_devices = false
                $scope.set_index_visibility(true)
                $("div#center_deviceinfo").hide()
        $scope.set_index_visibility = (flag) ->
            $scope.set_visibility(flag)
        root.show_device_on_index = $scope.use_devs
        # hack for late init of sidebar_base
        root.target_devsel_link = [$scope.use_devs, true]
        #root.install_devsel_link($scope.use_devs, true)
]).controller("sidebar_base", ["$scope", "$compile", "restDataSource", "$q", "$timeout", "Restangular", "$window",
    ($scope, $compile, restDataSource, $q, $timeout, Restangular, $window) ->
        $scope.index_view = $window.INDEX_VIEW
        $scope.searchstr = ""
        $scope.search_ok = true
        $scope.is_loading = true
        # active tab, (g)roups, (f)qdn, (c)ategories
        $scope.hidden_tabs = {"g" : true, "f" : true, "c" : true}
        $scope.devsel_func = []
        $scope.call_devsel_func = (called_after_load) ->
            if $scope.devsel_func.length or true
                # list of devices
                dev_pk_list = []
                # list of devices without meta device list
                dev_pk_nmd_list = []
                # list of device groups
                devg_pk_list = []
                # list of metadevices
                dev_pk_md_list = []
                for idx in $scope.cur_sel
                    if idx of $scope.dev_lut
                        # in case dev_lut is not valid
                        if $scope.dev_lut[idx].device_type_identifier == "MD"
                            devg_pk_list.push($scope.dev_lut[idx].device_group)
                            dev_pk_md_list.push(idx)
                        else
                            dev_pk_nmd_list.push(idx)
                        dev_pk_list.push(idx)
                #$scope.icsw_devsel.dev_pk_list = dev_pk_list
                #$scope.icsw_devsel.dev_pk_nmd_list = dev_pk_nmd_list
                #$scope.icsw_devsel.devg_pk_list = devg_pk_list
                #$scope.icsw_devsel.dev_pk_md_list = dev_pk_md_list
                for entry in $scope.devsel_func
                    if called_after_load and not entry.fire_when_loaded
                        true
                    else
                        # build device, device_group list
                        if entry.with_meta_devices
                            entry.func(dev_pk_list, devg_pk_list, dev_pk_md_list)
                        else
                            entry.func(dev_pk_nmd_list, devg_pk_list, dev_pk_md_list)
        $scope.resolve_device_keys = (key_list) =>
            list_len = key_list.length
            ret_list = list_len + (if list_len == 1 then " device" else " devices")
            if list_len
                if typeof(key_list[0]) == "int"
                    ret_list = "#{ret_list}: " + ($scope.dev_lut[key.split("__")[1]].full_name for key in key_list).join(", ")
                else
                    ret_list = "#{ret_list}: " + ($scope.dev_lut[key].full_name for key in key_list).join(", ")
            return ret_list
        $scope.update_search = () ->
            if $scope.cur_search_to
                $timeout.cancel($scope.cur_search_to)
            $scope.cur_search_to = $timeout($scope.set_search_filter, 500)
        $scope.set_search_filter = () ->
            try
                cur_re = new RegExp($scope.searchstr, "gi")
            catch exc
                cur_re = new RegExp("^$", "gi")
            cur_tree = $scope.get_tc($scope.active_tab) 
            cur_tree.toggle_tree_state(undefined, -1, false)
            num_found = 0
            cur_tree.iter(
                (entry, cur_re) ->
                    if entry._node_type == "d"
                        _sel = if $scope.dev_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                cur_re
            )
            $scope.search_ok = if num_found > 0 then true else false
            cur_tree.show_selected(false)
            $scope.selection_changed()
        # current device selection
        $scope.cur_sel = []            
        $scope.install_devsel_link = (ds_func, with_meta_devices) ->
            fire_when_loaded = true
            $scope.devsel_func.push({"func" : ds_func, "fire_when_loaded" : fire_when_loaded, "with_meta_devices" : with_meta_devices})
        if root.target_devsel_link?
            $scope.install_devsel_link(root.target_devsel_link[0], root.target_devsel_link[1])
            root.target_devsel_link = null
        root.install_devsel_link = $scope.install_devsel_link
        root.resolve_device_keys = $scope.resolve_device_keys
        root.sidebar = {"resolve_device_keys" : $scope.resolve_device_keys}
        $scope.active_tab = "{{ request.session.sidebar_mode }}".slice(0, 1) 
        $scope.tabs = {}
        for tab_short in ["g", "f", "c"]
            $scope.tabs[tab_short] = tab_short == $scope.active_tab
        $scope.rest_data = {}
        # olp is the object level permission
        #console.log "{{ device_object_level_permission }}"
        $scope.rest_map = [
            {
                "short" : "device_tree",
                "url" : "{% url 'rest:device_tree_list' %}",
                "options" : {
                    "ignore_cdg" : false
                    "tree_mode" : true
                    "all_devices" : true
                    "with_categories" : true
                    "olp" : "{{ device_object_level_permission }}"
                }
            } 
            {"short" : "domain_tree_node", "url" : "{% url 'rest:domain_tree_node_list' %}"}
            {"short" : "category", "url" : "{% url 'rest:category_list' %}"}
            {"short" : "device_sel", "url" : "{% url 'rest:device_selection_list' %}"}
        ]
        $scope.reload = (pk_list) ->
            if pk_list?
                # only reload the given devices
                # build list of current values
                prev_list = ([$scope.dev_lut[pk].domain_tree_node, (_entry for _entry in $scope.dev_lut[pk].categories)] for pk in pk_list)
                Restangular.all("{% url 'rest:device_tree_list' %}".slice(1)).getList({"pks" : angular.toJson(pk_list), "ignore_cdg" : false, "tree_mode" : true, "with_categories" : true, "olp" : "{{ device_object_level_permission }}"}).then((data) ->
                    $scope.update_device(data, prev_list)
                )
            else
                wait_list = []
                for value, idx in $scope.rest_map
                    $scope.rest_data[value.short] = restDataSource.reload([value.url, value.options])
                    wait_list.push($scope.rest_data[value.short])
                $q.all(wait_list).then((data) ->
                    for value, idx in data
                        $scope.rest_data[$scope.rest_map[idx].short] = value
                    $scope.rest_data_set()
                )
        # load from server
        $scope.reload()
        $scope.get_tc = (short) ->
            return {"g" : $scope.tc_devices, "f" : $scope.tc_fqdns, "c" : $scope.tc_categories}[short]
        $scope.set_active_selection = (t_type, new_sel) ->
            return $scope.get_tc(t_type).set_selected(
                (entry, new_sel) ->
                    if entry._node_type == "d"
                        return entry.obj in new_sel
                    else
                        # unknown node, return null
                        return null
                new_sel
            )
        $scope.get_active_selection = (t_type) ->
            return $scope.get_tc(t_type).get_selected(
                (entry) ->
                    if entry._node_type == "d" and entry.selected
                        return [entry.obj]
                    else
                        return []
            )
        $scope.clear_selection = () ->
            $scope.get_tc($scope.active_tab).clear_selected()
            $scope.search_ok = true
            $scope.selection_changed()
        $scope.activate_tab = (t_type) ->
            if $scope.hidden_tabs[t_type]
                $scope.hidden_tabs[t_type] = false
                switch t_type
                    when "g"
                        $scope.s_tc_devices = $scope.tc_devices
                    when "f"
                        $scope.s_tc_fqdns = $scope.tc_fqdns
                    when "c"
                        $scope.s_tc_categories = $scope.tc_categories
            cur_sel = $scope.get_active_selection($scope.active_tab)
            $scope.set_active_selection(t_type, cur_sel)
            $scope.active_tab = t_type
            call_ajax
                url  : "{% url 'user:set_user_var' %}"
                data : 
                    key   : "sidebar_mode"
                    value : {"c" : "category", "f" : "fqdn", "g" : "group"}[$scope.active_tab]
                    type  : "str"
        $scope.selection_changed = () ->
            cur_sel = $scope.get_active_selection($scope.active_tab)
            # cast to string to compare the arrays
            if String(cur_sel) != String($scope.cur_sel)
                $scope.cur_sel = cur_sel
                call_ajax
                    url     : "{% url 'device:set_selection' %}"
                    data    : {
                        "angular_sel" : angular.toJson(cur_sel)
                    }
                    success : (xml) ->
                        parse_xml_response(xml)
        # treeconfig for devices
        $scope.tc_devices = new sidebar_tree($scope, {show_tree_expand_buttons : false, show_descendants : true})
        # treeconfig for FQDN
        $scope.tc_fqdns = new sidebar_tree($scope, {show_childs : true})
        # treeconfig for categories
        $scope.tc_categories = new sidebar_tree($scope, {show_selection_buttons : true, show_descendants : true})
        $scope.update_device = (new_devs, prev_list) ->#prev_dtn, prev_cats) ->
            for info_tuple in _.zip(new_devs, prev_list)
                new_dev = info_tuple[0]
                prev_dtn = info_tuple[1][0]
                prev_cats = info_tuple[1][1]
                $scope.dev_lut[new_dev.idx] = new_dev
                prev_node = $scope.t_fqdn_lut[prev_dtn]
                # get previous node
                del_c = (entry for entry in prev_node.children when entry.obj == new_dev.idx)[0]
                # remove it
                prev_node.remove_child(del_c)
                # add new node
                $scope.t_fqdn_lut[new_dev.domain_tree_node].add_child($scope.tc_fqdns.new_node({obj : new_dev.idx, _node_type : "d", selected:new_dev.idx in $scope.cur_sel}))
                # migrate categories
                for prev_cat in prev_cats
                    prev_node = $scope.t_cat_lut[prev_cat]
                    del_c = (entry for entry in prev_node.children when entry.obj == new_dev.idx)[0]
                    prev_node.remove_child(del_c)
                cat_list = []
                for new_cat in new_dev.categories
                    cat_entry = $scope.tc_categories.new_node({obj:new_dev.idx, _node_type:"d", selected:new_dev.idx in $scope.cur_sel})
                    $scope.t_cat_lut[new_cat].add_child(cat_entry)
                    cat_list.push(cat_entry)
                if cat_list.length > 1
                    for cat_entry in cat_list
                        cat_entry.linklist = cat_list
            for cur_tc in [$scope.tc_devices, $scope.tc_fqdns, $scope.tc_categories]
                cur_tc.prune(
                    (entry) ->
                        return entry._node_type == "d"
                )
                cur_tc.recalc()
                cur_tc.show_selected()
        $scope.rest_data_set = () ->
            # clear root nodes
            $scope.tc_devices.clear_root_nodes()
            $scope.tc_fqdns.clear_root_nodes()
            $scope.tc_categories.clear_root_nodes()
            # build FQDNs tree
            $scope.fqdn_lut = {}
            # tree FQDN lut
            $scope.t_fqdn_lut = {}
            for entry in $scope.rest_data["domain_tree_node"]
                $scope.fqdn_lut[entry.idx] = entry
                t_entry = $scope.tc_fqdns.new_node({folder : true, obj:entry.idx, _node_type : "f", expand:entry.depth == 0})
                $scope.t_fqdn_lut[entry.idx] = t_entry
                if entry.parent
                    $scope.t_fqdn_lut[entry.parent].add_child(t_entry)
                else
                    $scope.tc_fqdns.add_root_node(t_entry)
            # build category tree
            $scope.cat_lut = {}
            # tree category lut
            $scope.t_cat_lut = {}
            for entry in $scope.rest_data["category"]
                $scope.cat_lut[entry.idx] = entry
                t_entry = $scope.tc_categories.new_node({folder : true, obj:entry.idx, _node_type : "c", expand:entry.depth == 0})
                $scope.t_cat_lut[entry.idx] = t_entry
                if entry.parent
                    $scope.t_cat_lut[entry.parent].add_child(t_entry)
                else
                    $scope.tc_categories.add_root_node(t_entry)
            # build devices tree
            $scope.dev_lut = {}
            cur_dg = undefined
            dsel_list = (entry.idx for entry in $scope.rest_data["device_sel"] when entry.sel_type == "d")
            $scope.cur_sel = dsel_list
            # we dont need the group selection
            # gsel_list = (entry.idx for entry in $scope.rest_data["device_sel"] when entry.sel_type == "g")
            for entry in $scope.rest_data["device_tree"]
                $scope.dev_lut[entry.idx] = entry
                # copy selection state to device selection (the selection state of the meta devices is keeped in sync with the selection states of the devicegroups )
                t_entry = $scope.tc_devices.new_node({obj:entry.idx, folder:entry.is_meta_device, _node_type:"d", selected:entry.idx in dsel_list})
                $scope.t_fqdn_lut[entry.domain_tree_node].add_child($scope.tc_fqdns.new_node({obj:entry.idx, _node_type:"d", selected:entry.idx in dsel_list}))
                if entry.categories
                    cat_list = []
                    for t_cat in entry.categories
                        cat_entry = $scope.tc_categories.new_node({obj:entry.idx, _node_type:"d", selected:entry.idx in dsel_list})
                        cat_list.push(cat_entry)
                        $scope.t_cat_lut[t_cat].add_child(cat_entry)
                    if cat_list.length > 1
                        for cat_entry in cat_list
                            cat_entry.linklist = cat_list
                if entry.is_meta_device
                    cur_dg = t_entry
                    $scope.tc_devices.add_root_node(cur_dg)
                else
                    cur_dg.add_child(t_entry)
            for cur_tc in [$scope.tc_devices, $scope.tc_fqdns, $scope.tc_categories]
                cur_tc.prune(
                    (entry) ->
                        return entry._node_type == "d"
                )
                cur_tc.recalc()
                cur_tc.show_selected()
            $scope.is_loading = false
            $scope.call_devsel_func(true)
])

root.angular_add_password_controller = angular_add_password_controller

root.sidebar_target_func = undefined
root.sidebar_call_devsel_link_when_loaded = false

{% endinlinecoffeescript %}

</script>
