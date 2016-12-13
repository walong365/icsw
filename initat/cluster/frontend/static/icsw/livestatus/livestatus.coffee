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
    "icsw.livestatus.livestatus",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
        "icsw.panel_tools",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.livestatus")
]).service("icswDeviceLivestatusTools",
[
    "$q", "$rootScope", "$templateCache", "$compile", "icswComplexModalService",
    "icswLivestatusPipeSpecTreeService", "icswToolsSimpleModalService", "blockUI",
    "icswMonDisplayPipeSpecBackup", "toaster", "icswUserGroupRoleTools",
(
    $q, $rootScope, $templateCache, $compile, icswComplexModalService,
    icswLivestatusPipeSpecTreeService, icswToolsSimpleModalService, blockUI,
    icswMonDisplayPipeSpecBackup, toaster, icswUserGroupRoleTools,
) ->
    modify_layout = (event, lsps_tree, connector) ->
        _prev_running = connector.set_running_flag(false)
        sub_scope = $rootScope.$new(true)
        sub_scope.connector = connector
        connector.start_recording()
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.connect.modify.layout"))(sub_scope)
                title: "Modify Layout (Dendrogram)"
                ok_label: "Modify"
                closable: true
                css_class: ""
                ok_callback: (modal) =>
                    d = $q.defer()
                    connector.stop_recording()
                    if connector.check_for_new_struct()
                        connector.object.json_spec = angular.toJson(connector.active_struct)
                        lsps_tree.modify_spec(connector.object).then(
                            (done) ->
                                d.resolve("saved")
                            (notok) ->
                                d.reject("not saved")
                        )
                    else
                        d.resolve("nothing")
                    return d.promise
                cancel_callback: (modal) =>
                    d = $q.defer()
                    connector.stop_recording()
                    if connector.records.length
                        # reverse connector records
                        for entry in _.reverse(connector.records)
                            parent_struct = connector.get_struct_by_id(entry.struct.parent_id)
                            if entry.action == "add"
                                # remove element
                                struct = connector.get_struct_by_id(entry.struct.id)
                                connector.delete_element(struct)

                            else
                                # add element
                                connector.create_and_add_element(parent_struct, entry.struct.name)
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) =>
                sub_scope.$destroy()
                connector.set_running_flag(_prev_running)
        )

    modify_spec = (lsps_tree, user, spec) ->
        sub_scope = $rootScope.$new(true)
        sub_scope.lsps_tree = lsps_tree
        sub_scope.spec = spec
        dbu = new icswMonDisplayPipeSpecBackup()
        dbu.create_backup(spec)

        sub_scope.pipe_spec_var_names = icswUserGroupRoleTools.pipe_spec_var_names()
        sub_scope.valid_for = {}
        # console.log "S=", spec.$$default_vars, spec
        for _vn in sub_scope.pipe_spec_var_names
            sub_scope.valid_for[_vn] = _vn in spec.$$default_vars
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.connect.show.pipe.modify"))(sub_scope)
                title: "Edit Pipesetup"
                ok_label: "ok"
                closable: true
                ok_callback: (modal) =>
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "")
                        d.reject("form not valid")
                    else
                        blockUI.start()
                        _var_q = $q.defer()
                        sub_scope.lsps_tree.modify_spec(spec).then(
                            (done) ->
                                _var_wait = []
                                for _vn, _flag of sub_scope.valid_for
                                    if _flag
                                        _var_wait.push(user.set_var(_vn, spec.name, "s"))
                                    else
                                        _var_wait.push(user.set_var(_vn, lsps_tree.get_default_layout(_vn), "s"))
                                $q.all(_var_wait).then(
                                    (done) ->
                                        lsps_tree.ensure_defaults().then(
                                            (done) ->
                                                # console.log "d=", done
                                                lsps_tree.build_luts()
                                                blockUI.stop()
                                                d.resolve("modified")
                                        )
                                )
                            (error) ->
                                blockUI.stop()
                                d.resolve("not modified")
                        )
                    return d.promise
                cancel_callback: (modal) =>
                    console.log "CANCEL"
                    dbu.restore_backup(spec)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) =>
                sub_scope.$destroy()
        )

    show_overview = (user) ->
        sub_scope = $rootScope.$new(true)
        icswLivestatusPipeSpecTreeService.load(sub_scope.$id).then(
            (lsps_tree) ->
                lsps_tree.set_user(user)
                sub_scope.lsps_tree = lsps_tree

                sub_scope.copy_spec = ($event, spec) ->
                    blockUI.start()
                    sub_scope.lsps_tree.duplicate_spec(spec).then(
                        (done) ->
                            blockUI.stop()
                        (error) ->
                            blockUI.stop()
                    )

                sub_scope.delete_spec = ($event, spec) ->
                    icswToolsSimpleModalService("Really delete Spec '#{spec.name}' ?").then(
                        (ok) ->
                            blockUI.start()
                            sub_scope.lsps_tree.delete_spec(spec).then(
                                (ok) ->
                                    blockUI.stop()
                                (error) ->
                                    blockUI.stop()
                            )
                    )
                sub_scope.modify_spec = ($event, spec) ->
                    modify_spec(sub_scope.lsps_tree, user, spec)

                icswComplexModalService(
                    {
                        message: $compile($templateCache.get("icsw.connect.show.pipe.overview"))(sub_scope)
                        title: "Pipe Overview"
                        ok_label: "ok"
                        closable: true
                        ok_callback: (modal) =>
                            d = $q.defer()
                            d.resolve("created")
                            return d.promise
                    }
                ).then(
                    (fin) =>
                        sub_scope.$destroy()
                )
        )

    return {
        show_overview: (user) ->
            return show_overview(user)

        modify_layout: ($event, lsps_tree, connector) ->
            return modify_layout($event, lsps_tree, connector)
    }

]).controller("icswDeviceLiveStatusCtrl",
[
    "$scope", "$compile", "$templateCache", "Restangular", "icswUserService",
    "$q", "$timeout", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
    "icswDeviceLivestatusDataService", "icswLivestatusFilterService",
    "icswDeviceTreeService", "icswMonLivestatusPipeConnector", "$rootScope", "ICSW_SIGNALS",
    "icswLivestatusPipeSpecTreeService", "icswDeviceLivestatusTools",
(
    $scope, $compile, $templateCache, Restangular, icswUserService,
    $q, $timeout, icswTools, ICSW_URLS, icswSimpleAjaxCall,
    icswDeviceLivestatusDataService, icswLivestatusFilterService,
    icswDeviceTreeService, icswMonLivestatusPipeConnector, $rootScope, ICSW_SIGNALS,
    icswLivestatusPipeSpecTreeService, icswDeviceLivestatusTools,
) ->
    # top level controller of monitoring dashboard

    _cd = {
        "btest": {
            "icswLivestatusSelDevices": [{
                "icswLivestatusDataSource": [{
                    "icswLivestatusFilterService": [{
                        "icswLivestatusLocationDisplay": []
                    }
                    {
                        "icswLivestatusMonCategoryFilter": [{
                            "icswLivestatusMapDisplay": []
                        }]
                    }
                    {
                        "icswLivestatusFilterService": [{
                            "icswLivestatusMonTabularDisplay": []
                        }
                            {
                                "icswLivestatusMonTabularDisplay": []
                            }]
                    }]
                }
                {
                    "icswLivestatusFilterService": [{
                        "icswLivestatusFullBurst": [{
                            "icswLivestatusMonTabularDisplay": []
                        }
                            {
                                "icswLivestatusFullBurst": []
                            }]
                    }]
                }
                {
                    "icswLivestatusFilterService": [{
                        "icswLivestatusLocationDisplay": []
                    }]
                }]
            }]
        }
    }

    $scope.struct = {
        # loading
        loading: true
        # data valid
        data_valid: false
        # active connector
        connector: null
        # connector name to use
        connector_name: null
        # user_var name to use for new connector
        user_var_name: null
        # connector is set
        connector_set: false
        # livestatuspipspectree
        lsps_tree: undefined
        # current user
        user: undefined
    }

    load = () ->
        $scope.struct.loading = true
        $q.all(
            [
                icswLivestatusPipeSpecTreeService.load($scope.$id)
                icswUserService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.lsps_tree = data[0]
                $scope.struct.user = data[1]
                $scope.struct.lsps_tree.set_user($scope.struct.user).then(
                    (done) ->
                        $scope.struct.loading = false
                        $scope.struct.data_valid = true
                        activate_connector()
                )
        )

    activate_connector = () ->
        if $scope.struct.data_valid and not $scope.struct.connector_set
            cn_set = $q.defer()
            if $scope.struct.user_var_name
                if $scope.struct.user.has_var($scope.struct.user_var_name)
                    cn_set.resolve($scope.struct.user.get_var($scope.struct.user_var_name).value)
                else
                    cn_set.reject("no")
            else if $scope.struct.connector_name
                cn_set.resolve($scope.struct.connector_name)
            else
                cn_set.reject("no")
            cn_set.promise.then(
                (c_name) ->
                    if $scope.struct.lsps_tree.spec_name_defined(c_name)
                        $scope.struct.connector = new icswMonLivestatusPipeConnector($scope.struct.lsps_tree.get_spec(c_name), $scope.struct.user)
                        $scope.struct.connector_set = true
                    else
                        console.error "pipe with spec name '#{c_name}' not defined"
                (not_set) ->
                    console.error "no valid connector name found"
            )

    load()

    $scope.unset_connector = () ->
        if $scope.struct.connector_set
            $scope.struct.connector.close()
            $scope.struct.connector_set = false
            $scope.struct.connector_name = null
            $scope.struct.connector = null

    $scope.set_connector = (c_name) ->
        $scope.unset_connector()
        $scope.struct.user_var_name = null
        $scope.struct.connector_name = c_name
        activate_connector()

    $scope.set_connector_via_var = (v_name) ->
        $scope.unset_connector()
        $scope.struct.user_var_name = v_name
        $scope.struct.connector_name = null
        activate_connector()

    $scope.toggle_gridster_lock = () ->
        if $scope.struct.connector_set
            $scope.struct.connector.toggle_global_display_state()
            is_unlocked = $scope.struct.connector.global_display_state == 1
            $scope.struct.connector.gridsterOpts.resizable.enabled = is_unlocked
            $scope.struct.connector.gridsterOpts.draggable.enabled = is_unlocked
            $rootScope.$emit(ICSW_SIGNALS("ICSW_TRIGGER_PANEL_LAYOUTCHECK"))

    $scope.modify_layout = ($event) ->
        if $scope.struct.connector_set
            icswDeviceLivestatusTools.modify_layout($event, $scope.struct.lsps_tree, $scope.struct.connector)

    $scope.new_devsel = (_dev_sel) ->
        if $scope.struct.connector_set
            # console.log "nds"
            $scope.struct.connector.new_devsel(_dev_sel)

    $scope.pipe_overview = ($event) ->
        icswDeviceLivestatusTools.show_overview($scope.struct.user)

    $scope.$on("$destroy", () ->
        if $scope.struct.connector
            $scope.struct.connector.close()
    )

]).directive("icswDeviceLivestatus",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.livestatus.connect.overview")
        controller: "icswDeviceLiveStatusCtrl"
        scope:
            active_view: "=icswLivestatusView"
            var_name: "=icswVarName"
        link: (scope, element, attrs) ->
            if attrs.icswVarName?
                scope.$watch(
                    "var_name"
                    (new_val) ->
                        if new_val?
                            scope.set_connector_via_var(new_val)
                        else
                            scope.unset_connector()
                )
                true
            else
                scope.$watch(
                    "active_view"
                    (new_val) ->
                        if new_val?
                            scope.set_connector(new_val)
                        else
                            scope.unset_connector()
                )
    }
])
