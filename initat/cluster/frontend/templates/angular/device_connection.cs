{% load i18n coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}
device_connection_template = """
<div>
    <h2>Device connections, {{ cd_devs.length }} controlling devices selected</h2>
    <table ng-show="cd_devs.length" class="table table-condensed table-hover" style="width:auto;">
        <tbody>
            <tr ng-repeat-start="dev in cd_devs" class="success">
                <th colspan="2">{{ dev.full_name }} ({{ dev.comment }})</th>
            </tr>
            <tr>
                <td>
                    <div class="input-group-btn">
                        <div class="btn-group" ng-show="any_valid_devs(dev, false)">
                            <button class="btn btn-success dropdown-toggle btn-sm" data-toggle="dropdown">
                                is master for <span class="caret"></span>
                            </button>
                            <ul class="dropdown-menu">
                                <li ng-repeat="pk in get_valid_devs(dev, false)">
                                    <a href="#" ng-click="create_master(dev, pk)">{{ get_device_info(pk) }}</a>
                                </li>
                            </ul>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="input-group-btn">
                        <div class="btn-group" ng-show="any_valid_devs(dev, true)">
                            <button class="btn btn-success dropdown-toggle btn-sm" data-toggle="dropdown">
                                is slave of <span class="caret"></span>
                            </button>
                            <ul class="dropdown-menu">
                                <li ng-repeat="pk in get_valid_devs(dev, true)">
                                    <a href="#" ng-click="create_slave(dev, pk)">{{ get_device_info(pk) }}</a>
                                </li>
                            </ul>
                        </div>
                    </div>
                </td>
            </tr>
            <tr>
                <td><ng-pluralize count="dev.slave_list.length" when="{'0' : 'no slave devices', '1' : 'one slave device', 'other' : '{} slave devices'}"</ng-pluralize></td>
                <td><ng-pluralize count="dev.master_list.length" when="{'0' : 'no master devices', '1' : 'one master device', 'other' : '{} master devices'}"</ng-pluralize></td>
            </tr>
            <tr ng-repeat-end>
                <td>
                    <ul class="list-group">
                        <li ng-repeat="el in dev.slave_list" class="list-group-item">
                            <button class="btn btn-xs btn-danger" ng-click="delete_cd(el, dev, $event)">delete</button>&nbsp;
                            <button class="btn btn-xs btn-warning" ng-click="modify_cd(el, $event)">modify</button>
                            {{ el.child | follow_fk:this:'devices':'full_name' }}
                            ({{ el.connection_info }}; {{ el.parameter_i1 }} / 
                            {{ el.parameter_i2 }} / 
                            {{ el.parameter_i3 }} / 
                            {{ el.parameter_i4 }})
                        </li>
                    </ul>
                </td>
                <td>
                    <ul class="list-group">
                        <li ng-repeat="el in dev.master_list" class="list-group-item">
                            <button class="btn btn-xs btn-danger" ng-click="delete_cd(el, dev, $event)">delete</button>&nbsp;
                            <button class="btn btn-xs btn-warning" ng-click="modify_cd(el, $event)">modify</button>
                            {{ el.parent | follow_fk:this:'devices':'full_name' }}
                            ({{ el.connection_info }}; {{ el.parameter_i1 }} / 
                            {{ el.parameter_i2 }} / 
                            {{ el.parameter_i3 }} / 
                            {{ el.parameter_i4 }}) 
                        </li>
                    </ul>
                </td>
            </tr>
        </tbody>
    </table>
    <h3>Automatic creation</h3>
    <form class="form-inline">
        Set
        <div class="form-group">
            <input type="text" class="form-control" ng-model="ac_host"></input> 
        </div>
        (Host) as <input type="button" class="btn btn-sn btn-primary" ng-value="ac_type" ng-click="change_ac_type()"></input>
        for
        <div class="form-group">
            <input type="text" class="form-control" ng-model="ac_cd"></input> 
        </div>
        (Controlling device)
        <input type="button" ng-show="ac_host && ac_cd" class="btn btn-success" value="create" ng-click="handle_ac()"></input>
    </form>
    Example: 'node##' as Slave for 'ipmi##' (2 digits).
</div>
"""

{% endverbatim %}

device_connection_module = angular.module("icsw.device.connection", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"])

device_connection_module.controller("connection_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "blockUI", "icswTools",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, blockUI, icswTools) ->
        $scope.devsel_list = []
        # ac settings
        $scope.ac_type = "master"
        $scope.change_ac_type = () ->
            $scope.ac_type = if $scope.ac_type == "master" then "slave" else "master"
        $scope.handle_ac = () ->
            blockUI.start()
            call_ajax
                url   : "{% url 'device:manual_connection' %}"
                data  : {
                    "source" : $scope.ac_host
                    "target" : $scope.ac_cd
                    "mode"   : $scope.ac_type
                }
                success : (xml) =>
                    blockUI.stop()
                    # show info
                    parse_xml_response(xml, 30)
                    # reload (even on error)
                    $scope.reload()
        # mixins
        $scope.cd_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.cd_edit.create_template = "cd.connection.form"
        $scope.cd_edit.edit_template = "cd.connection.form"
        $scope.cd_edit.create_rest_url = Restangular.all("{% url 'rest:cd_connection_list'%}".slice(1))
        $scope.cd_edit.modify_rest_url = "{% url 'rest:cd_connection_detail' 1 %}".slice(1).slice(0, -2)
        $scope.cd_edit.new_object_at_tail = true
        $scope.cd_edit.use_promise = true

        $scope.new_devsel = (_dev_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.reload()
        $scope.reload = () ->
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                ["{% url 'rest:device_tree_list' %}", {"pks" : angular.toJson($scope.devsel_list), "cd_connections" : true, "olp" : "backbone.device.change_connection"}],
                ["{% url 'rest:cd_connection_list' %}", {}]
            ])
            $q.all(wait_list).then((data) ->
                _devs = data[0]
                $scope.devices = icswTools.build_lut(_devs)
                $scope.cd_devs = []
                for entry in _devs
                    if entry.device_type_identifier == "CD" and entry.idx in $scope.devsel_list
                        entry.master_list = []
                        entry.slave_list = []
                        $scope.cd_devs.push(entry)
                $scope.cd_lut = icswTools.build_lut($scope.cd_devs)
                for _cd in data[1]
                    if _cd.parent of $scope.cd_lut
                        $scope.cd_lut[_cd.parent].slave_list.push(_cd)
                    if _cd.child of $scope.cd_lut
                        $scope.cd_lut[_cd.child].master_list.push(_cd)
            )
        $scope.modify_cd = (cd, event) ->
            $scope.cd_edit.edit(cd, event).then(
                (mod_cd) ->
                    if mod_cd != false
                        # nothing
                        true
            )
        $scope.delete_cd = (cd, dev, event) ->
            $scope.cd_edit.delete_list = undefined
            $scope.cd_edit.delete_obj(cd).then(
                (do_it) ->
                    if do_it
                        dev.master_list = (entry for entry in dev.master_list when entry.idx != cd.idx)
                        dev.slave_list  = (entry for entry in dev.slave_list  when entry.idx != cd.idx)
            )
        $scope.any_valid_devs = (dev, only_cds) ->
            return if $scope.get_valid_devs(dev, only_cds).length then true else false
        $scope.get_valid_devs = (dev, only_cds) ->
            # return all valid devices for given cd
            _ms_pks = (entry.child for entry in dev.master_list).concat((entry.parent for entry in dev.slave_list))
            valid_pks = (pk for pk in $scope.devsel_list when pk != dev.idx and pk not in _ms_pks)
            if only_cds
                valid_pks = (pk for pk in valid_pks when pk of $scope.devices and $scope.devices[pk].device_type_identifier == "CD")
            return valid_pks
        $scope.get_device_info = (pk) ->
            if pk of $scope.devices
                return $scope.devices[pk].full_name
            else
                return "#{pk} ?"
        $scope.create_master = (dev, pk) ->
            new_obj = {
                "parent" : dev.idx
                "child"  : pk
                "connection_info" : "from webfrontend"
                "created_by" : CURRENT_USER.pk
            }
            $scope.cd_edit.create_rest_url.post(new_obj).then((data) ->
                dev.slave_list.push(data)
            )
        $scope.create_slave = (dev, pk) ->
            new_obj = {
                "parent" : pk
                "child"  : dev.idx
                "connection_info" : "from webfrontend"
                "created_by" : CURRENT_USER.pk
            }
            $scope.cd_edit.create_rest_url.post(new_obj).then((data) ->
                dev.master_list.push(data)
            )
    ]
).directive("deviceconnection", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("device_connection_template.html")
        link : (scope, el, attrs) ->
            scope.$watch(attrs["devicepk"], (new_val) ->
                if new_val and new_val.length
                    scope.new_devsel(new_val)
            )
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[0])                    
                )
    }
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("device_connection_template.html", device_connection_template)
)
{% endinlinecoffeescript %}

</script>

