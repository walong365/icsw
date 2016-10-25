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
    icswRouteExtensionProvider.add_route("main.devicemonconfig")
]).service("icswDeviceConfigHelper",
[
    "$q", "$rootScope", "ICSW_SIGNALS", "icswSimpleAjaxCall", "ICSW_URLS",
(
    $q, $rootScope, ICSW_SIGNALS, icswSimpleAjaxCall, ICSW_URLS,
) ->

    # helper service for config changes

    class icswDeviceConfigHelper
        constructor: (@mode, @device_tree, @config_tree) ->
            # list of active configs or check commands or server commands
            @active_rows = []
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
                    # build name value to match against
                    if @mode == "gen"
                        conf.$$_dc_name = conf.name
                    else
                        conf.$$_dc_num_mcs = conf.mon_check_command_set.length
                        conf.$$_dc_name = ("#{_v.name} #{_v.description}" for _v in conf.mon_check_command_set).join(" ")
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

        update_active_rows: (name_re, only_selected, with_server, with_service) =>
            @active_rows.length = 0

            for entry in @config_tree.list
                entry.$selected = if (entry.enabled and entry.$$_dc_name.match(name_re)) then true else false
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
                    if @mode == "gen"
                        @active_rows.push(entry)
                    else
                        for _mc in entry.mon_check_command_set
                            @active_rows.push(_mc)
            $rootScope.$emit(ICSW_SIGNALS("_ICSW_DEVICE_CONFIG_CHANGED"))

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

]).directive("icswDeviceConfigOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    # assign general configs
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.device.config.overview")
        controller: "icswDeviceConfigCtrl"
        link: (scope, element, attrs) ->
            scope.set_mode("gen")
    }
]).directive("icswDeviceMonConfigOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    # assign general configs
    return {
        scope: true
        restrict : "EA"
        template : $templateCache.get("icsw.device.config.overview")
        controller: "icswDeviceConfigCtrl"
        link: (scope, element, attrs) ->
            scope.set_mode("mon")
    }
]).controller("icswDeviceConfigCtrl",
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
    $scope.struct = {
        # matrix view open
        matrix: true
        # icswDeviceConfigHelper
        helper: undefined
        # name filter
        name_filter: ""
        # only selected configs
        only_selected: false
        # show server configs
        with_server: 0
        # show service configs
        with_service: 0
        # overall mode
        mode: ""
        # device tree
        device_tree: undefined
        # config tree
        config_tree: undefined
        # new config name
        new_config_name: ""
    }

    _mode_wait = $q.defer()
    $scope.set_mode = (mode) ->
        _mode_wait.resolve(mode)

    $scope.new_devsel = (_dev_sel) ->
        local_defer = $q.defer()
        if not $scope.struct.device_tree
            _mode_wait.promise.then(
                (mode) ->
                    $scope.struct.mode = mode
                    $scope.struct.info_str = {
                        "gen": "Configurations",
                        "mon": "Check commands",
                    }[$scope.struct.mode]
                    $q.all(
                        [
                            icswDeviceTreeService.load($scope.$id)
                            icswConfigTreeService.load($scope.$id)
                        ]
                    ).then(
                        (data) ->
                            $scope.struct.device_tree = data[0]
                            $scope.struct.config_tree = data[1]
                            $scope.struct.helper = new icswDeviceConfigHelper(
                                $scope.struct.mode
                                $scope.struct.device_tree
                                $scope.struct.config_tree
                            )
                            local_defer.resolve("init done")
                    )
            )
        else
            local_defer.resolve("already init")
        local_defer.promise.then(
            (init_msg) ->
                $scope.struct.helper.set_devices(_dev_sel)
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

        $scope.struct.helper.update_active_rows(cur_re, $scope.struct.only_selected, $scope.struct.with_server, $scope.struct.with_service)

    $scope.toggle_only_selected = () ->
        $scope.struct.only_selected = !$scope.struct.only_selected
        $scope.new_filter_set($scope.struct.name_filter, true)

    $scope.settings_changed = () ->
        if $scope.struct.helper?
            $scope.new_filter_set($scope.struct.name_filter, true)

    $scope.create_config = (cur_cat) ->
        blockUI.start()
        new_obj = {
            name: $scope.struct.new_config_name
            config_catalog: cur_cat.idx
            description: "QuickConfig"
            priority: 0
        }
        $scope.struct.helper.config_tree.create_config(new_obj).then(
            (new_conf) ->
                blockUI.stop()
                $scope.new_filter_set()
            (not_ok) ->
                blockUI.stop()
        )

]).service("icswDeviceConfigTableReact",
[
    "$q", "blockUI",
(
    $q, blockUI,
)->
    {table, thead, div, tr, span, th, td, tbody} = React.DOM
    rot_header = React.createFactory(
        React.createClass(
            propTypes: {
                rowElement: React.PropTypes.object
                configHelper: React.PropTypes.object
            }
            getInitialState: () ->
                return {
                    mouse: false
                }
            render: () ->
                re = @props.rowElement
                if @props.configHelper.mode == "gen"
                    _info_str = re.$$info_str
                    _title_str = re.$$long_info_str
                else
                    _title_str = "#{re.description} (#{re.name})"
                    _info_str = _title_str.substr(0, 24)
                return th(
                    {
                        className: "icsw-config-rotate"
                    }
                    div(
                        {
                            onMouseEnter: (event) =>
                                @setState({mouse: true})
                            onMouseLeave: (event) =>
                                @setState({mouse: false})
                            title: _title_str
                        }
                        span(
                            {
                                key: "text1"
                            }
                            _info_str
                        )
                        if @state.mouse then span(
                            {
                                key: "text2"
                                className: "label label-primary"
                            }
                            "selected"
                        ) else null
                    )
                )
        )
    )
    head_factory = React.createFactory(
        React.createClass(
            propTypes: {
                configHelper: React.PropTypes.object
            }
            render: () ->
                _conf_headers = [
                    rot_header(
                        {
                            key: "conf#{row_el.idx}"
                            rowElement: row_el
                            configHelper: @props.configHelper
                        }
                    ) for row_el in @props.configHelper.active_rows
                ]
                _conf_infos = []
                for row_el in @props.configHelper.active_rows
                    if @props.configHelper.mode == "gen"
                        _conf = row_el
                    else
                        _conf = row_el.$$config
                    _conf_infos.push(
                        th(
                            {
                                key: "info-#{row_el.idx}"
                                className: "text-center"
                            }
                            span(
                                {
                                    key: "span"
                                    className: "label label-primary"
                                }
                                _conf.$$config_type_str
                            )
                        )
                    )
                return thead(
                    {key: "head"}
                    tr(
                        {key: "head"}
                        th(
                            {
                                key: "head"
                                colSpan: 3
                            }
                        )
                        _conf_headers
                    )
                    tr(
                        {key: "info"}
                        th({key: "t0"}, "Type")
                        td({key: "t1"}, "Local")
                        td({key: "t2"}, "Meta")
                        _conf_infos
                    )
                )
        )
    )
    td_factory = React.createFactory(
        React.createClass(
            propTypes: {
                configHelper: React.PropTypes.object
                device: React.PropTypes.object
                rowElement: React.PropTypes.object
            }
            render: () ->
                _el = @props.rowElement
                if @props.configHelper.mode == "gen"
                    _conf = _el
                else
                    _conf = _el.$$config
                [_class, _icon] = @props.configHelper.get_td_class_and_icon(@props.device, _conf)
                return td(
                    {
                        className: "text-center #{_class}"
                        onClick: (event) =>
                            if @props.configHelper.click_allowed(@props.device, _conf)
                                blockUI.start()
                                @props.configHelper.click(@props.device, _conf).then(
                                    (ok) ->
                                        blockUI.stop()
                                )
                    }
                    span(
                        {className: _icon}
                    )
                )
        )
    )
    row_factory = React.createFactory(
        React.createClass(
            propTypes: {
                configHelper: React.PropTypes.object
                device: React.PropTypes.object
            }
            render: () ->
                dev = @props.device
                if dev.is_meta_device
                    [_name, _class] = ["Group", "warning"]
                else
                    [_name, _class] = [dev.full_name, ""]
                return tr(
                    {}
                    th(
                        {key: "head", className: _class}
                        _name
                    )
                    td(
                        {key: "local", className: "text-center"}
                        dev.$local_selected.length
                    )
                    td(
                        {key: "meta", className: "text-center"}
                        if dev.is_meta_device then "" else dev.$num_meta_selected
                    )
                    [
                        td_factory(
                            {
                                configHelper: @props.configHelper
                                rowElement: row_el
                                device: dev
                            }
                        ) for row_el in @props.configHelper.active_rows
                    ]

                )
        )
    )
    tbody_factory = React.createFactory(
        React.createClass(
            propTypes: {
                configHelper: React.PropTypes.object
                groupStruct: React.PropTypes.object
            }
            render: () ->
                return tbody(
                    {}
                    tr(
                        {key: "info", className: "info"}
                        th(
                            {colSpan: 999, style: {paddingTop: "6px", paddingBottom: "6px"}}
                            "DeviceGroup #{@props.groupStruct.group.name}"
                        )
                    )
                    [
                        row_factory(
                            {
                                configHelper: @props.configHelper
                                device: dev
                            }
                        ) for dev in @props.groupStruct.devices
                    ]
                )
        )
    )
    return React.createClass(
        propTypes: {
            configHelper: React.PropTypes.object
        }
        render: () ->
            if not @props.configHelper.devices.length
                return null
            table(
                {
                    key: "top"
                    className: "table rotateheaders table-condensed table-hover colhover"
                    style: {width: "auto"}
                }
                head_factory(
                    {
                        configHelper: @props.configHelper
                    }
                )
                [
                    tbody_factory(
                        {
                            configHelper: @props.configHelper
                            groupStruct: group
                        }
                    ) for group in @props.configHelper.groups
                ]
            )
    )
]).directive("icswDeviceConfigReact",
[
    "$templateCache", "$compile", "$rootScope", "ICSW_SIGNALS", "blockUI",
    "icswDeviceConfigTableReact",
(
    $templateCache, $compile, $rootScope, ICSW_SIGNALS, blockUI,
    icswDeviceConfigTableReact,
) ->
    return {
        restrict: "EA"
        scope: {
            helper: "=icswConfigHelper"
        }
        link: (scope, element, attrs) ->
            _element = ReactDOM.render(
                React.createElement(
                    icswDeviceConfigTableReact
                    {
                        configHelper: scope.helper
                        configGeneration: scope.helper.generation
                    }
                )
                element[0]
            )
            $rootScope.$on(ICSW_SIGNALS("_ICSW_DEVICE_CONFIG_CHANGED"), (event, helper) ->
                _element.forceUpdate()
            )
    }
])
