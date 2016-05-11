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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

angular.module(
    "icsw.device.config",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.deviceconfig"
            {
                url: "/deviceconfig"
                templateUrl: "icsw/main/device/config.html"
                icswData:
                    pageTitle: "Configure Device"
                    rights: ["device.change_config"]
                    menuEntry:
                        menukey: "dev"
                        name: "Device Configurations"
                        icon: "fa-check-square"
                        ordering: 10
            }
    )
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
            @devices = []

        set_devices: (dev_list) =>
            # create a copy of the device list, otherwise
            # the list could be changed from icsw-sel-man without
            # the necessary helper objects ($local_selected)
            @devices.length = 0
            for dev in dev_list
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
            $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_CONFIG_CHANGED"))

        show_config: (dev, conf) ->
            if conf?
                if dev.is_meta_device and conf.server_config
                    return false
                else
                    return true
            else
                return false

        get_td_class: (dev, conf, single_line) =>
            _cls = ""
            is_meta_dev = dev.is_meta_device
            meta_dev = @md_lut[dev.idx]
            if single_line and not @show_config(dev, conf)
                _cls = "danger"
            if conf?
                if conf.idx in dev.$local_selected
                    _cls = "success"
                else if conf in meta_dev.$local_selected and not is_meta_dev
                    _cls = "warn"
            return _cls

        get_config_class_icon: (dev, conf, single_line) =>
            if single_line
                _cls = "glyphicon glyphicon-minus"
            else
                _cls = "glyphicon"
            if conf?
                is_meta_dev = dev.is_meta_device
                meta_dev = @md_lut[dev.idx]
                if conf.idx in dev.$local_selected
                    _cls = "glyphicon glyphicon-ok"
                if conf.idx in meta_dev.$local_selected and not is_meta_dev
                    _cls = "glyphicon glyphicon-ok-circle"
            return _cls

        update_active_configs: (name_re, only_selected, with_system) =>
            @active_configs.length = 0

            for entry in @config_tree.list
                entry.$selected = if (entry.enabled and entry.name.match(name_re)) then true else false
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
                if not with_system and entry.system_config
                    entry.$selected = false
                if entry.$selected
                    @active_configs.push(entry)
            $rootScope.$emit(ICSW_SIGNALS("ICSW_DEVICE_CONFIG_CHANGED"))

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

    $scope.name_filter = ""
    $scope.new_config_name = ""
    $scope.matrix = true
    $scope.struct = {
        # only selected configs
        only_selected: false
        # show system configs
        with_system: true
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
                # create instance with $local_selected,
                # $scope.helper = new icswDeviceConfigHelper($scope.device_tree, $scope.config_tree, _dev_sel)
                $scope.$watch("name_filter", (new_val) ->
                    if $scope.filter_to?
                        $timeout.cancel($scope.filter_to)
                    $scope.filter_to = $timeout(
                        $scope.new_filter_set_exp
                        500
                    )
                )

                $scope.new_filter_set()
        )

    # filter functions

    $scope.new_filter_set_exp = () ->
        $scope.new_filter_set()

    $scope.new_filter_set = () ->
        # called after filter settings have changed
        try
            cur_re = new RegExp($scope.name_filter, "gi")
        catch exc
            cur_re = new RegExp("^$", "gi")

        $scope.helper.update_active_configs(cur_re, $scope.struct.only_selected, $scope.struct.with_system)

    $scope.toggle_only_selected = () ->
        $scope.struct.only_selected = !$scope.struct.only_selected
        $scope.new_filter_set($scope.name_filter, true)

    $scope.toggle_with_system = () ->
        $scope.struct.with_system = !$scope.struct.with_system
        $scope.new_filter_set($scope.name_filter, true)

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
            return obj.full_name.slice(8) + " [Group]"
        else
            return obj.full_name

    $scope.get_th_class = (dev) ->
        if dev.is_meta_device
            return "warning"
        else
            return ""

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
                _td_el.addClass("text-center " + scope.helper.get_td_class(scope.device, conf, true))
                if scope.helper.show_config(scope.device, conf)
                    _td_el.append(angular.element("<span class='" + scope.helper.get_config_class_icon(scope.device, conf, true) + "'></span>"))
                else
                    _td_el.append(angular.element("<span class='glyphicon glyphicon-remove-sign'></span>"))

            _handle_click = (conf, _td_el) ->
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
            $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_CONFIG_CHANGED"), (event, helper) ->
                _redraw_line()
            )
            _redraw_line()
    }
])
