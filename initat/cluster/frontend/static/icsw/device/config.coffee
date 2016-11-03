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
    icswRouteExtensionProvider.add_route("main.devicesrvconfig")
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
            # total elements in row
            @num_rows = 0
            # render counter
            @render_count = 0
            # pending changes
            @pending = {
                clicked: []
            }
            # config stream (for changes)
            @pc_stream = {}

            @check_pending()

        set_devices: (dev_list) =>
            # create a group dict
            _group_lut = {}
            @groups = []
            for dev in dev_list
                dg_idx = dev.device_group
                if dg_idx not of _group_lut
                    _new_struct = {
                        "group": dev.$$group
                        "meta": dev.$$meta_device
                        "devices": []
                        # number of non-meta devices
                        "nmd_count": 0
                    }
                    _group_lut[dg_idx] = _new_struct
                    @groups.push(_new_struct)
                if @mode == "srv" and dev.is_meta_device
                    # do not add meta-devices to srv-mode view
                    true
                else
                    _group_lut[dg_idx]["devices"].push(dev)
                if not dev.is_meta_device
                    _group_lut[dg_idx]["nmd_count"]++

            if @mode == "srv"
                # depending on mode filter out all groups where only the meta-device is selected
                @groups = (entry for entry in @groups when entry.nmd_count > 0)
            _group_ids = (entry.group.idx for entry in @groups)
            # create a copy of the device list, otherwise
            # the list could be changed from icsw-sel-man without
            # the necessary helper objects ($local_selected)
            @devices.length = 0
            for dev in dev_list
                if dev.device_group in _group_ids
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

            for conf in @config_tree.list
                if @mode in ["gen", "srv"]
                    conf.$$_dc_name = conf.name
                else
                    conf.$$_dc_num_mcs = conf.mon_check_command_set.length
                    conf.$$_dc_name = ("#{_v.name} #{_v.description}" for _v in conf.mon_check_command_set).join(" ")
                for dev in @md_list
                    # build name value to match against
                    _id = "#{dev.idx}::#{conf.idx}"
                    for dc in conf.device_config_set
                        if dc.device == dev.idx
                            dev.$local_selected.push(conf.idx)
                    # if _id in @pending.added
                    #    dev.$local_selected.push(conf.idx)

                # step 3: set configs for all non-meta-devices

                for dev in @non_md_list
                    _id = "#{dev.idx}::#{conf.idx}"
                    for dc in conf.device_config_set
                        if dc.device == dev.idx
                            dev.$local_selected.push(conf.idx)

                # step 4: apply changes

                if conf.idx of @pc_stream
                    _pcs = @pc_stream[conf.idx]
                    _meta = @md_lut
                    for _token in _pcs
                        if _token < 0
                            # click on meta device
                            md = @md_lut[-_token]
                            if conf.idx in md.$local_selected
                                # deselect
                                _.remove(md.$local_selected, (entry) -> return entry == conf.idx)
                            else
                                # select
                                md.$local_selected.push(conf.idx)
                                # deselect all local selections
                                for dev_idx in md.$$group.devices
                                    if dev_idx != md.idx
                                        dev = @device_tree.all_lut[dev_idx]
                                        if dev.$local_selected?
                                            _.remove(dev.$local_selected, (entry) -> return entry == conf.idx)
                        else
                            dev = @device_tree.all_lut[_token]
                            md = @md_lut[_token]
                            if conf.idx in md.$local_selected
                                # handle meta device
                                # deselect from meta device
                                _.remove(md.$local_selected, (entry) -> return entry == conf.idx)
                                # select all other devices
                                for dev_idx in md.$$group.devices
                                    if dev_idx != md.idx and dev_idx != dev.idx
                                        @device_tree.all_lut[dev_idx].$local_selected.push(conf.idx)
                            else
                                if conf.idx in dev.$local_selected
                                    # deselect local
                                    _.remove(dev.$local_selected, (entry) -> return entry == conf.idx)
                                else
                                    # select local
                                    dev.$local_selected.push(conf.idx)

            # count selected

            for dev in @non_md_list
                dev.$num_meta_selected = @md_lut[dev.idx].$local_selected.length
            @render_count++
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
            @num_rows = 0

            for entry in @config_tree.list
                if entry.enabled
                    if @mode == "srv"
                        if not entry.$$cse or not entry.server_config
                            continue
                    entry.$selected = entry.$$_dc_name.match(name_re)
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
                    if @mode == "gen"
                        # only apply filter when handling general configs
                        if with_server == 1 and not entry.server_config
                            entry.$selected = false
                        else if with_server == -1 and entry.server_config
                            entry.$selected = false
                        if with_service == 1 and not entry.$$cse
                            entry.$selected = false
                        else if with_service == -1 and entry.$$cse
                            entry.$selected = false
                    if entry.$selected
                        if @mode in ["gen", "srv"]
                            @active_rows.push(entry)
                        else
                            for _mc in entry.mon_check_command_set
                                @active_rows.push(_mc)
                    # count rows
                    if @mode in ["gen", "srv"]
                        @num_rows++
                    else
                        @num_rows += entry.mon_check_command_set.length
            @render_count++
            $rootScope.$emit(ICSW_SIGNALS("_ICSW_DEVICE_CONFIG_CHANGED"))

        click: (device, config) =>
            defer = $q.defer()
            [_dev_idx, _conf_idx, _meta_idx] = [device.idx, config.idx, @md_lut[device.idx].idx]
            _id = "#{_dev_idx}::#{_conf_idx}::#{_meta_idx}"
            @pending.clicked.push(_id)
            # interpret
            # build config streams, key is config idx
            conf_stream = {}
            for _id in @pending.clicked
                _parts = _id.split("::")
                _dev_idx = parseInt(_parts[0])
                _conf_idx = parseInt(_parts[1])
                _meta_idx = parseInt(_parts[2])
                if _conf_idx not of conf_stream
                    conf_stream[_conf_idx] = []
                _cs = conf_stream[_conf_idx]
                if _dev_idx == _meta_idx
                    _token = -_meta_idx
                else
                    _token = _dev_idx
                _cs.push(_token)

            @pc_stream = conf_stream
            # console.log @pc_stream
            @check_pending()
            @link()
            defer.resolve("done")
            return defer.promise

        check_pending: () =>
            if @pending.clicked.length
                @any_pending = true
            else
                @any_pending = false

        remove_pending: () =>
            @pending.clicked.length = 0
            @pc_stream = {}
            @check_pending()
            @link()

        commit_changes: () =>
            defer = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.CONFIG_ALTER_CONFIG_CB
                    data: {
                        stream_data: angular.toJson(
                            (
                                {
                                    meta_pk: parseInt(_id.split("::")[2])
                                    dev_pk: parseInt(_id.split("::")[0])
                                    conf_pk: parseInt(_id.split("::")[1])
                                }
                            ) for _id in @pending.clicked
                        )
                    }
                }
            ).then(
                (xml) =>
                    # console.log "xml=", xml
                    $(xml).find("changeset > config").each (idx, config_entry) =>
                        _idx = parseInt($(config_entry).attr("pk"))
                        config = @config_tree.lut[_idx]
                        config.device_config_set.length = 0
                        $(config_entry).find("entry").each (idx, add_entry) =>
                            # add new entries
                            add_entry = $(add_entry)
                            config.device_config_set.push(
                                {
                                    device: parseInt(add_entry.attr("device"))
                                    config: parseInt(add_entry.attr("config"))
                                    idx: parseInt(add_entry.attr("pk"))
                                }
                            )
                    @remove_pending()
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
]).directive("icswDeviceSrvConfigOverview",
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
            scope.set_mode("srv")
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
                        "srv": "System services ",
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
    "$q", "blockUI", "icswConfigMonCheckCommandListService", "icswMonitoringBasicTreeService",
    "$rootScope",
(
    $q, blockUI, icswConfigMonCheckCommandListService, icswMonitoringBasicTreeService,
    $rootScope,
)->
    {table, thead, div, tr, span, th, td, tbody, button} = React.DOM
    rot_header = React.createFactory(
        React.createClass(
            propTypes: {
                rowElement: React.PropTypes.object
                configHelper: React.PropTypes.object
                focus: React.PropTypes.bool
            }
            getInitialState: () ->
                return {
                    mouse: false
                }
            render: () ->
                re = @props.rowElement
                if @props.configHelper.mode in ["gen", "srv"]
                    _info_str = re.$$info_str
                    _title_str = re.$$long_info_str
                else
                    _title_str = "#{re.description} (#{re.name})"
                    _info_str = _title_str
                _focus = @state.mouse or @props.focus
                if _focus
                    _classname = "bg-danger cursorpointer"
                else
                    _classname = "cursorpointer"
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
                            onClick: (event) =>
                                if @props.configHelper.mode in ["mon"]
                                    icswMonitoringBasicTreeService.load("config_edit").then(
                                        (mon_tree) =>
                                            icswConfigMonCheckCommandListService.create_or_edit(
                                                $rootScope
                                                event
                                                false
                                                @props.rowElement
                                                @props.configHelper.config_tree
                                                mon_tree
                                            ).then(
                                                (done) =>
                                                    @props.configHelper.link()
                                            )
                                    )
                                else
                                    console.error "not implemented"
                        }
                        span(
                            {
                                key: "text1"
                                className: _classname
                            }
                            _info_str
                        )
                        # if _focus then span(
                        #    {
                        #        key: "text2"
                        #        className: "label label-danger"
                        #    }
                        #    "*"
                        # ) else null
                    )
                )
        )
    )
    head_factory = React.createFactory(
        React.createClass(
            propTypes: {
                configHelper: React.PropTypes.object.isRequired
                focusElement: React.PropTypes.number
            }
            render: () ->
                _conf_headers = []
                _conf_infos = []
                _last_idx = 0
                _mark_header = false
                for row_el in @props.configHelper.active_rows
                    if @props.configHelper.mode in ["gen", "srv"]
                        _conf = row_el
                    else
                        _conf = row_el.$$config
                    if @props.focusElement
                        _focus = _conf.idx == @props.focusElement
                    else
                        _focus = false
                    if _conf.idx != _last_idx
                        _last_idx = _conf.idx
                        _mark_header = !_mark_header
                    _conf_headers.push(
                        rot_header(
                            {
                                key: "conf#{row_el.idx}"
                                rowElement: row_el
                                configHelper: @props.configHelper
                                focus: _focus
                            }
                        )
                    )
                    _conf_infos.push(
                        th(
                            {
                                key: "info-#{row_el.idx}"
                                className: ["text-center", if _mark_header then "bg-success" else "bg-warning"].join(" ")
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
                if @props.configHelper.any_pending
                    modify_button = button(
                        {
                            key: "modify"
                            type: "button"
                            className: "btn btn-sm btn-primary"
                            onClick: (event) =>
                                blockUI.start()
                                @props.configHelper.commit_changes().then(
                                    (done) =>
                                        blockUI.stop()
                                )

                        }
                        "Modify"
                    )
                    cancel_button = button(
                        {
                            key: "cancel"
                            type: "button"
                            className: "btn btn-sm btn-warning"
                            onClick: (event) =>
                                @props.configHelper.remove_pending()
                        }
                        "Cancel"
                    )
                else
                    modify_button = null
                    cancel_button = null
                return thead(
                    {key: "head"}
                    tr(
                        {key: "head"}
                        th(
                            {
                                key: "head"
                                colSpan: 3
                            }
                            modify_button
                            cancel_button
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
                focusCallback: React.PropTypes.func.isRequired
            }

            getInitialState: () ->
                return {focus: false}
            render: () ->
                _el = @props.rowElement
                if @props.configHelper.mode in ["gen", "srv"]
                    _conf = _el
                    _info_str = _el.$$info_str
                else
                    _conf = _el.$$config
                    _info_str = "#{_el.description} (#{_el.name})"
                [_class, _icon] = @props.configHelper.get_td_class_and_icon(@props.device, _conf)
                if @state.focus
                    _class = "#{_class} bg-primary"
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
                        onMouseEnter: (event) =>
                            @setState({focus: true})
                            @props.focusCallback(_conf, true)
                        onMouseLeave: (event) =>
                            @setState({focus: false})
                            @props.focusCallback(_conf, false)
                        title: _info_str
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
                focusCallback: React.PropTypes.func.isRequired
            }
            getInitialState: () ->
                return {counter: 0}

            shouldComponentUpdate: (next_props, next_state) ->
                # very simple update cache, compare local render count with counter from config
                _doit = false
                if @props.configHelper.render_count != @state.counter
                    @setState({counter: @props.configHelper.render_count})
                    _doit = true
                return _doit

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
                                focusCallback: @props.focusCallback
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
                focusCallback: React.PropTypes.func.isRequired
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
                                focusCallback: @props.focusCallback
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

        getInitialState: () ->
            return {
                counter: 0
                # idx of focused element (integer of config)
                focus_el: 0
            }

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        render: () ->
            focus_cb = (el, state) =>
                if state
                    @setState({focus_el: el.idx})
                else
                    if @state.focus_el
                        @setState({focus_el: 0})

            if not @props.configHelper.devices.length
                return null

            table(
                {
                    key: "top"
                    className: "table rotateheaders table-condensed table-hover colhover"
                    style: {width: "auto", overflowX: "auto", display: "block"}
                }
                head_factory(
                    {
                        configHelper: @props.configHelper
                        focusElement: @state.focus_el
                    }
                )
                [
                    tbody_factory(
                        {
                            configHelper: @props.configHelper
                            groupStruct: group
                            focusCallback: focus_cb
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
