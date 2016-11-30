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

monitoring_basic_module = angular.module(
    "icsw.monitoring.monitoring_basic",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
        "icsw.tools.table", "icsw.tools.button"
    ]
).directive("icswMonitoringBasic",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.monitoring.basic")
        controller: "icswMonitoringBasicCtrl"
    }
]).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.monitorbasics")
]).directive("icswMonitoringSetup",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    console.log "ms"
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.monitoring.setup")
        scope: true
    }

]).controller("icswMonitoringBasicCtrl",
[
    "$scope", "$q", "icswMonitoringBasicTreeService",
(
    $scope, $q, icswMonitoringBasicTreeService
) ->
    $scope.struct = {
        # tree valid
        tree_valid: false
        # basic tree
        basic_tree: undefined
    }
    $scope.reload = () ->
        icswMonitoringBasicTreeService.load($scope.$id).then(
            (data) ->
                $scope.struct.basic_tree = data
                $scope.struct.tree_valid = true
                # console.log $scope.struct
        )
    $scope.reload()

]).service("icswMonitoringUtilService",
[
    "icswComplexModalService", "$compile", "$templateCache", "$q", "toaster",
    "Restangular", "ICSW_URLS",
(
    icswComplexModalService, $compile, $templateCache, $q, toaster,
    Restangular, ICSW_URLS,
) ->
    # helper functions for monitoring_basic
    _device_list_warned = false

    return {
        get_data_incomplete_error: (tree, table) ->
            if not tree?
                return "missing tree"
            if not table of tree.missing_info
                ret = ""
            else
                missing = []
                for _tuple in tree.missing_info[table]
                    if _tuple.length == 3
                        # handle extra reference name
                        [_ref, model_name, human_name] = _tuple
                        _ref = tree[_ref]
                    else
                        _ref = tree
                        [model_name, human_name] = _tuple
                    _list_name = "#{model_name}_list"
                    if _list_name of _ref
                        if not _ref[_list_name].length
                            missing.push(human_name)
                    else
                        if _list_name == "device_list"
                            if not _device_list_warned
                                console.warn "device_list is not set in cluster_tree, fixme"
                                _device_list_warned = true
                        else
                            console.error "missing list #{_list_name}"

                if missing.length
                    missing_str = ("a #{n}" for n in missing).join(" and ")
                    ret = "Please add #{missing_str}"
                else
                    ret = ""
            return ret

        create_or_edit: (tree, scope, create, obj, obj_name, bu_def, template_name, template_title)  ->
            if not create
                dbu = new bu_def()
                dbu.create_backup(obj)
            # new sub_scope
            sub_scope = scope.$new(false)
            sub_scope.create = create
            sub_scope.edit_obj = obj

            # for fields, tree can be the basic or the cluster tree
            sub_scope.tree = tree
            if scope.user_group_tree?
                sub_scope.user_group_tree = scope.user_group_tree
            if scope.device_tree?
                sub_scope.device_tree = scope.device_tree
            if tree.basic_tree?
                sub_scope.basic_tree = tree.basic_tree

            # form error
            sub_scope.form_error = (field_name) ->
                if sub_scope.form_data[field_name].$valid
                    return ""
                else
                    return "has-error"

            icswComplexModalService(
                {
                    message: $compile($templateCache.get(template_name))(sub_scope)
                    title: template_title
                    css_class: ""
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "")
                            d.reject("form not valid")
                        else
                            if create
                                tree["create_#{obj_name}"](sub_scope.edit_obj).then(
                                    (new_period) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                _URL = ICSW_URLS["REST_" + _.toUpper(obj_name) + "_DETAIL"].slice(1).slice(0, -2)
                                Restangular.restangularizeElement(null, sub_scope.edit_obj, _URL)
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        tree.build_luts()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    sub_scope.$destroy()
            )

    }
]).service("icswMonitoringBasicPeriodService",
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonPeriodBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonPeriodBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_period_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    alias: "new period"
                    mon_range: "00:00-24:00"
                    tue_range: "00:00-24:00"
                    wed_range: "00:00-24:00"
                    thu_range: "00:00-24:00"
                    fri_range: "00:00-24:00"
                    sat_range: "00:00-24:00"
                    sun_range: "00:00-24:00"
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_period"
                icswMonPeriodBackup
                "icsw.mon.period.form"
                "Monitoring Period"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringPeriod '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_period(obj).then(
                        () ->
                            console.log "mon_period deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_period")
    }
]).service('icswMonitoringBasicNotificationService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonNotificationBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonNotificationBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_notification_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    channel: "mail"
                    not_type: "service"
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_notification"
                icswMonNotificationBackup
                "icsw.mon.notification.form"
                "Monitoring Notification"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringNotification '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_notification(obj).then(
                        () ->
                            console.log "mon_not deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_notification")
    }
]).service('icswMonitoringBasicServiceTemplateService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonServiceTemplBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonServiceTemplBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_service_templ_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    nsn_period: basic_tree.mon_period_list[0].idx
                    nsc_period: basic_tree.mon_period_list[0].idx
                    max_attempts: 1
                    ninterval: 2
                    check_interval: 2
                    retry_interval: 2
                    nrecovery: true
                    ncritical: true
                    low_flap_threshold: 20
                    high_flap_threshold: 80
                    freshness_threshold: 60
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_service_templ"
                icswMonServiceTemplBackup
                "icsw.mon.service.templ.form"
                "Monitoring Service Template"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringServiceTemplate '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_service_templ(obj).then(
                        () ->
                            console.log "mon_service_templ deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_service_templ")
    }
]).service('icswMonitoringBasicDeviceTemplateService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonDeviceTemplBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonDeviceTemplBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_device_templ_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    mon_service_templ: basic_tree.mon_service_templ_list[0].idx
                    host_check_command: basic_tree.host_check_command_list[0].idx
                    mon_period: basic_tree.mon_period_list[0].idx
                    not_period: basic_tree.mon_period_list[0].idx
                    max_attempts: 1
                    ninterval: 5
                    check_interval: 2
                    retry_interval: 2
                    nrecovery: true
                    ndown: true
                    ncritical: true
                    low_flap_threshold: 20
                    high_flap_threshold: 80
                    freshness_threshold: 60
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_device_templ"
                icswMonDeviceTemplBackup
                "icsw.mon.device.templ.form"
                "Monitoring Device Template"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringDeviceTemplate '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_device_templ(obj).then(
                        () ->
                            console.log "mon_device_templ deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_device_templ")
    }
]).service('icswMonitoringBasicHostCheckCommandService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswHostCheckCommandBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswHostCheckCommandBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.host_check_command_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    command_line: ""
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "host_check_command"
                icswHostCheckCommandBackup
                "icsw.host.check.command.form"
                "Monitoring Host Check Command"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete HostCheckCommand '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_host_check_command(obj).then(
                        () ->
                            console.log "host_check_command deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "host_check_command")
    }
]).service('icswMonitoringBasicMonContactService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular", "icswUserGroupRoleTreeService",
    "icswToolsSimpleModalService", "icswMonContactBackup", "icswMonitoringUtilService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular, icswUserGroupRoleTreeService,
    icswToolsSimpleModalService, icswMonContactBackup, icswMonitoringUtilService,
) ->
    basic_tree = undefined
    user_group_tree = undefined

    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringBasicTreeService.load(scope.$id)
                    icswUserGroupRoleTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    basic_tree = data[0]
                    user_group_tree = data[1]

                    for obj in basic_tree.mon_contact_list
                        obj.loginname = user_group_tree.user_lut[obj.user].login

                    scope.basic_tree = basic_tree
                    scope.user_group_tree = user_group_tree
                    scope.getters = {
                        nsc_period: (value) ->
                            return basic_tree.mon_period_lut[value].name

                        nsn_period: (value) ->
                            return basic_tree.mon_period_lut[value].name
                    }

                    defer.resolve(basic_tree.mon_contact_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    user: user_group_tree.user_list[0].idx
                    snperiod: basic_tree.mon_period_list[0].idx
                    hnperiod: basic_tree.mon_period_list[0].idx
                    snrecovery: true
                    sncritical: true
                    hnrecovery: true
                    hndown: true
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_contact"
                icswMonContactBackup
                "icsw.mon.contact.form"
                "Monitoring Contact"
            )

        get_notifications: (obj) ->
            _list = []
            for mnt in obj.notifications
                mnt = basic_tree.mon_notification_lut[mnt]
                _list.push(mnt.name)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringContact '#{obj.idx}' ?").then(
                () =>
                    basic_tree.delete_mon_contact(obj).then(
                        () ->
                            console.log "mon_contact deleted"
                    )
            )

        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "mon_contact")
    }
]).service('icswMonitoringBasicMonContactgroupService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular", "icswUserGroupRoleTreeService",
    "icswToolsSimpleModalService", "icswMonContactgroupBackup", "icswMonitoringUtilService",
    "icswDeviceTreeService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular, icswUserGroupRoleTreeService,
    icswToolsSimpleModalService, icswMonContactgroupBackup, icswMonitoringUtilService,
    icswDeviceTreeService,
) ->
    basic_tree = undefined
    user_group_tree = undefined
    device_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            $q.all(
                [
                    icswMonitoringBasicTreeService.load(scope.$id)
                    icswUserGroupRoleTreeService.load(scope.$id)
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    basic_tree = data[0]
                    user_group_tree = data[1]
                    device_tree = data[2]
                    scope.basic_tree = basic_tree
                    scope.user_group_tree = user_group_tree
                    scope.device_tree = device_tree
                    defer.resolve(basic_tree.mon_contactgroup_list)
            )
            return defer.promise
            
        get_members: (obj) ->
            _list = []
            for member in obj.members
                user = user_group_tree.user_lut[basic_tree.mon_contact_lut[member].user]
                _list.push(user.login)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        get_device_groups: (obj) ->
            _list = []
            for dg in obj.device_groups
                dg = device_tree.group_lut[dg]
                _list.push(dg.name)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        get_service_templates: (obj) ->
            _list = []
            for mst in obj.service_templates
                mst = basic_tree.mon_service_templ_lut[mst]
                _list.push(mst.name)
            if _list.length
                return _list.join(", ")
            else
                return "---"

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    alias: ""
                }
            return icswMonitoringUtilService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_contactgroup"
                icswMonContactgroupBackup
                "icsw.mon.contactgroup.form"
                "Monitoring Contact Group"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete ContactGroup '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_contactgroup(obj).then(
                        () ->
                            console.log "mon_contactgroup deleted"
                    )
            )
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(basic_tree, "host_contactgroup")
    }
])
