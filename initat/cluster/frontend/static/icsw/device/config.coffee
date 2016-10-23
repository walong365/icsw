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
    "icsw.device.config",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.deviceconfig")
]).service("icswDeviceConfigHelper",
[
    "$q", "$rootScope", "ICSW_SIGNALS", "icswSimpleAjaxCall", "ICSW_URLS",
(
    $q, $rootScope, ICSW_SIGNALS, icswSimpleAjaxCall, ICSW_URLS,
) ->

    # helper service for config changes

    class icswDeviceConfigHelper
        constructor: (@device_tree, @config_tree) ->
            console.log "ch init", @
            @active_configs = []
            # list of all groups
            @groups = []
            # list of all devices
            @devices = []

        set_devices: (dev_list) =>
            # create a copy of the device list, otherwise
            # the list could be changed from icsw-sel-man without
            # the necessary helper objects ($local_selected)
            _group_lut = {}
            @groups = []
            @devices.length = 0
            for dev in dev_list
                dg_idx = dev.device_group
                if dg_idx not of _group_lut
                    _new_struct = {
                        "group": dev.$$group
                        "meta": dev.$$meta_device
                        "devices": []
                    }
                    _group_lut[dg_idx] = _new_struct
                    @groups.push(_new_struct)
                _group_lut[dg_idx]["devices"].push(dev)
                @devices.push(dev)
            @link()

        link: () =>

            # step 1: identitfy all meta devices

            md_list = []
            non_md_list = []
            # lut: device idx to meta-device
            @md_lut = {}

            for dev in @devices
                dev.$local_selected = []
                dev.$num_meta_selected = 0
                if dev.is_meta_device
                    md_list.push(dev)
                    @md_lut[dev.idx] = dev
                else
                    non_md_list.push(dev)
                    md = @device_tree.get_meta_device(dev)
                    # the md_list + non_md_list may be longer than the @devices
                    md.$local_selected = []
                    md.$num_meta_selected = 0
                    if md not in md_list
                        md_list.push(md)
                    @md_lut[dev.idx] = md
            @md_list = md_list
            @non_md_list = non_md_list

            # step 2: set configs for all meta-devices

            for dev in @md_list
                for conf in @config_tree.list
                    for dc in conf.device_config_set
                        if dc.device == dev.idx
                            dev.$local_selected.push(conf.idx)

            # step 3: set configs for all non-meta-devices

            for dev in @non_md_list
                for conf in @config_tree.list
                    for dc in conf.device_config_set
                        if dc.device == dev.idx
                            dev.$local_selected.push(conf.idx)
                dev.$num_meta_selected = @md_lut[dev.idx].$local_selected.length
            $rootScope.$emit(ICSW_SIGNALS("_ICSW_DEVICE_CONFIG_CHANGED"))

        click_allowed: (dev, conf) =>
            if dev.is_meta_device and conf.server_config
                return false
            else
                return true

        get_td_class_and_icon: (dev, conf) =>
            if dev.is_meta_device and conf.server_config
                # check if config is a server config and therefore not selectable for
                # a meta device (== group)
                _cls = "danger"
                _icon = "glyphicon glyphicon-remove-sign"
            else if conf.idx in dev.$local_selected
                # config is locally selected
                _cls = "success"
                _icon = "glyphicon glyphicon-ok"
            else if conf.idx in @md_lut[dev.idx].$local_selected and not dev.is_meta_device
                # config is selected via meta-device (== group)
                _cls = "warn"
                _icon = "glyphicon glyphicon-ok-circle"
            else
                # config is not selected
                _cls = ""
                _icon = "glyphicon glyphicon-minus"
            return [_cls, _icon]

        update_active_configs: (name_re, only_selected, with_server, with_service) =>
            @active_configs.length = 0

            for entry in @config_tree.list
                entry.$selected = if (entry.enabled and entry.name.match(name_re)) then true else false
                @mouse_leave(entry)
                if only_selected and entry.$selected
                    entry.$selected = false
                    for cur_dev in @devices
                        if entry.idx in cur_dev.$local_selected
                            entry.$selected = true
                            break
                    # check for selected meta-devices
                    if not entry.$selected
                        for cur_md in @md_list
                            if entry.idx in cur_md.$local_selected
                                entry.$selected = true
                                break
                if with_server == 1 and not entry.server_config
                    entry.$selected = false
                else if with_server == -1 and entry.server_config
                    entry.$selected = false
                if with_service == 1 and not entry.$$cse
                    entry.$selected = false
                else if with_service == -1 and entry.$$cse
                    entry.$selected = false
                if entry.$selected
                    @active_configs.push(entry)
            $rootScope.$emit(ICSW_SIGNALS("_ICSW_DEVICE_CONFIG_CHANGED"))

        mouse_enter: (config) =>
            config.$$mouse = true
            config.$$header_class = "label label-primary"

        mouse_leave: (config) =>
            config.$$mouse = false
            config.$$header_class = "label label-default"

        click: (device, config) =>

            defer = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.CONFIG_ALTER_CONFIG_CB
                    data: {
                        meta_pk: @md_lut[device.idx].idx
                        dev_pk: device.idx
                        conf_pk: config.idx
                    }
                }
            ).then(
                (xml) =>
                    # clear config
                    config.device_config_set.length = 0
                    $(xml).find("config > device").each (idx, cur_dev) =>
                        cur_dev = $(cur_dev)
                        config.device_config_set.push(
                            {
                                device: parseInt(cur_dev.attr("device"))
                                config: parseInt(cur_dev.attr("config"))
                                idx: parseInt(cur_dev.attr("pk"))
                            }
                        )
                    @link()
                    defer.resolve("changed")

            )
            return defer.promise

]).controller("icswDeviceConfigurationCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal", "icswAcessLevelService",
    "icswTools", "ICSW_URLS", "$timeout", "icswDeviceTreeService", "blockUI",
    "icswConfigTreeService", "icswDeviceConfigHelper",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal, icswAcessLevelService,
    icswTools, ICSW_URLS, $timeout, icswDeviceTreeService, blockUI,
    icswConfigTreeService, icswDeviceConfigHelper,
) ->
    icswAcessLevelService.install($scope)
    $scope.device_tree = undefined
    $scope.config_tree = undefined

    # icswDeviceConfigHelper

    $scope.helper = undefined

    $scope.new_config_name = ""
    $scope.matrix = true
    $scope.struct = {
        # name filter
        name_filter: ""
        # only selected configs
        only_selected: false
        # show server configs
        with_server: 0
        # show service configs
        with_service: 0
    }
    $scope.new_devsel = (_dev_sel) ->
        local_defer = $q.defer()
        if not $scope.device_tree
            $q.all(
                [
                    icswDeviceTreeService.load($scope.$id)
                    icswConfigTreeService.load($scope.$id)
                ]
            ).then(
                (data) ->
                    $scope.device_tree = data[0]
                    $scope.config_tree = data[1]
                    $scope.helper = new icswDeviceConfigHelper($scope.device_tree, $scope.config_tree)
                    local_defer.resolve("init done")
            )
        else
            local_defer.resolve("already init")
        local_defer.promise.then(
            (init_msg) ->
                $scope.helper.set_devices(_dev_sel)

                $scope.new_filter_set()
        )

    # filter functions

    $scope.new_filter_set_exp = () ->
        $scope.new_filter_set()

    $scope.new_filter_set = () ->
        # called after filter settings have changed
        try
            cur_re = new RegExp($scope.struct.name_filter, "gi")
        catch exc
            cur_re = new RegExp("^$", "gi")

        $scope.helper.update_active_configs(cur_re, $scope.struct.only_selected, $scope.struct.with_server, $scope.struct.with_service)

    $scope.toggle_only_selected = () ->
        $scope.struct.only_selected = !$scope.struct.only_selected
        $scope.new_filter_set($scope.struct.name_filter, true)

    $scope.settings_changed = () ->
        if $scope.helper?
            $scope.new_filter_set($scope.struct.name_filter, true)

    $scope.create_config = (cur_cat) ->
        blockUI.start()
        new_obj = {
            name: $scope.new_config_name
            config_catalog: cur_cat.idx
            description: "QuickConfig"
            priority: 0
        }
        $scope.helper.config_tree.create_config(new_obj).then(
            (new_conf) ->
                blockUI.stop()
                $scope.new_filter_set()
            (not_ok) ->
                blockUI.stop()
        )

    # simple utility helper functions

    $scope.get_tr_class = (obj) ->
        if obj.is_meta_device
            return "success"
        else
            return ""

    $scope.get_name = (obj) ->
        if obj.is_meta_device
            return "Group"
        else
            return obj.full_name

    $scope.get_th_class = (dev) ->
        if dev.is_meta_device
            return "warning"
        else
            return ""

    # mouse enter / levae
    $scope.mouse_enter = ($event, config) ->
        $scope.helper.mouse_enter(config)

    $scope.mouse_leave = ($event, config) ->
        $scope.helper.mouse_leave(config)

]).directive("icswDeviceConfigurationOverview", ["$templateCache", ($templateCache) ->
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.device.configuration.overview")
        controller: "icswDeviceConfigurationCtrl"
    }
]).directive("icswDeviceConfigurationRowData",
[
    "$templateCache", "$compile", "$rootScope", "ICSW_SIGNALS", "blockUI",
(
    $templateCache, $compile, $rootScope, ICSW_SIGNALS, blockUI,
) ->
    return {
        restrict : "EA"
        scope: {
            helper: "="
            device: "="
        }
        link: (scope, el, attrs) ->

            _update_td_el = (conf, _td_el) ->
                _td_el.children().remove()
                _td_el.removeClass()
                [_class, _icon] = scope.helper.get_td_class_and_icon(scope.device, conf)
                _td_el.addClass("text-center #{_class}")
                _td_el.append(angular.element("<span class='#{_icon}'></span>"))

            _handle_click = (conf, _td_el) ->
                if scope.helper.click_allowed(scope.device, conf)
                    blockUI.start()
                    scope.helper.click(scope.device, conf).then(
                        (ok) ->
                            blockUI.stop()
                            _update_td_el(conf, _td_el)
                    )

            _create_td_el = (entry) ->
                _td_el = angular.element("<td></td>")
                _td_el.bind("click", (event) =>
                    _handle_click(entry, _td_el)
                )
                _update_td_el(entry, _td_el)
                return _td_el

            _redraw_line = () ->
                for _entry in _display
                    _entry.remove()
                for entry in scope.helper.active_configs
                    _td_el = _create_td_el(entry)
                    _display.push(_td_el)
                    _parent.append(_td_el)

            _parent = el.parent()
            el.remove()
            _display = []

            # scope.$watch("device._scc", (new_val) ->
            #     _redraw_line(scope.configs)
            # )
            $rootScope.$on(ICSW_SIGNALS("_ICSW_DEVICE_CONFIG_CHANGED"), (event, helper) ->
                _redraw_line()
            )
            _redraw_line()
    }
])
