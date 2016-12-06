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
                # clicked
                clicked: []
                # removed (for monitoring checks to be removed selectively)
                removed: []
            }
            # config stream (for changes)
            @pc_stream = {}

            @check_pending()

        set_devices: (dev_list) =>
            # create a group dict
            _group_lut = {}
            @dev_group_lut = {}
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
                # lookup table from device to group structure
                @dev_group_lut[dev.idx] = _group_lut[dg_idx]
                if @mode == "srv" and dev.is_meta_device
                    # do not add meta-devices to srv-mode view
                    true
                else
                    if dev.is_meta_device
                        _group_lut[dg_idx]["devices"].splice(0, 0, dev)
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
                # meta-devices will be filtered out in srv-view
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
                # configs local selected
                dev.$local_selected = []
                # configs -> mon_checks local removed
                dev.$local_removed = {}
                dev.$num_meta_selected = 0
                if dev.is_meta_device
                    md_list.push(dev)
                    @md_lut[dev.idx] = dev
                else
                    non_md_list.push(dev)
                    md = @device_tree.get_meta_device(dev)
                    # the md_list + non_md_list may be longer than the @devices
                    md.$local_selected = []
                    md.$local_removed = {}
                    md.$num_meta_selected = 0
                    if md not in md_list
                        md_list.push(md)
                    @md_lut[dev.idx] = md
            @md_list = md_list
            @non_md_list = non_md_list

            # step 1b: add exclude devices from mon_check_command

            for mc in @config_tree.mon_basic_tree.mon_check_command_list
                for dev in @devices
                    if dev.idx in mc.exclude_devices
                        if mc.config not of dev.$local_removed
                            dev.$local_removed[mc.config] = []
                        dev.$local_removed[mc.config].push(mc.idx)


            # step 2: set configs for all meta-devices

            for conf in @config_tree.list
                if @mode in ["gen", "srv"]
                    conf.$$_dc_name = conf.name
                else
                    conf.$$_dc_num_mcs = conf.mon_check_command_set.length
                    conf.$$_dc_name = ("#{_v.name} #{_v.description}" for _v in conf.mon_check_command_set).join(" ")
                for dev in @md_list
                    # build name value to match against
                    for dc in conf.device_config_set
                        if dc.device == dev.idx
                            dev.$local_selected.push(conf.idx)

                # step 3a: set configs for all non-meta-devices

                for dev in @non_md_list
                    for dc in conf.device_config_set
                        if dc.device == dev.idx
                            dev.$local_selected.push(conf.idx)

                # step 4: apply changes

                # helper functions

                _toggle_mon_check = (dev, conf_idx, mc_idx) ->
                    if conf_idx of dev.$local_removed and mc_idx in dev.$local_removed[conf_idx]
                        # remove entry when set
                        _.remove(dev.$local_removed[conf_idx], (entry) -> return entry == mc_idx)
                        if not dev.$local_removed[conf_idx].length
                            delete dev.$local_removed[conf_idx]
                    else
                        # add entry when not set
                        if conf_idx not of dev.$local_removed
                            dev.$local_removed[conf_idx] = []
                        dev.$local_removed[conf_idx].push(mc_idx)

                if conf.idx of @pc_stream
                    _pcs = @pc_stream[conf.idx]
                    for _token in _pcs
                        if _token.type == "m"
                            # click on meta device
                            meta_dev = @md_lut[_token.idx]
                            if conf.idx in meta_dev.$local_selected
                                # deselect
                                _.remove(meta_dev.$local_selected, (entry) -> return entry == conf.idx)

                            else
                                # select
                                meta_dev.$local_selected.push(conf.idx)
                                # deselect all local selections
                                for dev_idx in meta_dev.$$group.devices
                                    if dev_idx != meta_dev.idx
                                        dev = @device_tree.all_lut[dev_idx]
                                        if dev.$local_selected?
                                            _.remove(dev.$local_selected, (entry) -> return entry == conf.idx)
                        else
                            # click on device
                            dev = @device_tree.all_lut[_token.idx]
                            meta_dev = @md_lut[_token.idx]
                            if conf.idx in meta_dev.$local_selected
                                if @mode == "mon"
                                    _toggle_mon_check(dev, conf.idx, _token.element)
                                else
                                    # handle meta device
                                    # deselect from meta device
                                    _.remove(meta_dev.$local_selected, (entry) -> return entry == conf.idx)
                                    # select all other devices
                                    for dev_idx in meta_dev.$$group.devices
                                        if dev_idx != meta_dev.idx and dev_idx != dev.idx
                                            _loc_dev = @device_tree.all_lut[dev_idx]
                                            if _loc_dev.$local_selected?
                                                @device_tree.all_lut[dev_idx].$local_selected.push(conf.idx)
                            else
                                if conf.idx in dev.$local_selected
                                    if @mode == "mon"
                                        _toggle_mon_check(dev, conf.idx, _token.element)
                                    else
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

        get_td_class_and_icon: (row_el, conf, dev) =>
            # check shadow focus state
            _shadow = false
            _foc = false
            if dev.idx of @focus_dict
                if conf.idx of @focus_dict[dev.idx]
                    if @focus_dict[dev.idx][conf.idx]
                        _shadow = true
                        if @focus_element and @focus_element[0].idx == row_el.idx and @focus_element[1].idx == dev.idx
                            _foc = true
            if dev.is_meta_device and conf.server_config
                # check if config is a server config and therefore not selectable for
                # a meta device (== group)
                _cls = "danger"
                _icon = "fa fa-times-circle"
            else if conf.idx in dev.$local_selected
                # config is locally selected
                if conf.idx of dev.$local_removed and row_el.idx in dev.$local_removed[conf.idx]
                    # is locally removed
                    _cls = "danger"
                    _icon = "fa fa-times-rectangle-o"
                else
                    if _foc
                        _cls = "primary"
                        _icon = "fa fa-minus"
                    else
                        _cls = "success"
                        _icon = "fa fa-check"
            else if conf.idx in @md_lut[dev.idx].$local_selected and not dev.is_meta_device
                # config is selected via meta-device (== group)
                if conf.idx of dev.$local_removed and row_el.idx in dev.$local_removed[conf.idx]
                    _cls = "danger"
                    _icon = "fa fa-times-rectangle-o"
                else
                    _cls = "warning"
                    _icon = "fa fa-check-square-o"
            else
                # config is not selected
                if _foc
                    _icon = "fa fa-check"
                    _cls = "primary"
                else
                    _icon = "fa fa-minus"
                    if _shadow
                        _cls = "warning"
                    else
                        _cls = ""
            return [_cls, _icon]

        set_focus: (row_el, conf, device) =>
            @clear_focus()
            @focus_element = [row_el, device]
            _set_list = [device.idx]
            _group = @dev_group_lut[device.idx]
            if device.idx == _group.meta.idx
                for _dev in _group.devices
                    _set_list.push(_dev.idx)
            for _dev_idx in _set_list
                @focus_set_list.push([conf.idx, _dev_idx])
                @focus_dict[_dev_idx][conf.idx] = true
                @linedraw_dict[_dev_idx]++

        clear_focus: () =>
            for [_conf, _dev] in @focus_set_list
                @focus_dict[_dev][_conf] = false
                @linedraw_dict[_dev]++
            @focus_set_list.length = 0
            @focus_element = null

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

            # setup focus helper structurs
            @focus_dict = {}
            # indices of focus element
            @focus_element = null
            # list of indices of shadow selections (config, devicegroup)
            @focus_set_list = []
            @linedraw_dict = {}
            for group in @groups
                for dev in group.devices
                    @focus_dict[dev.idx] = {}
                    @linedraw_dict[dev.idx] = 0
                    for row in @active_rows
                        @focus_dict[dev.idx][row.idx] = false
            @render_count++
            $rootScope.$emit(ICSW_SIGNALS("_ICSW_DEVICE_CONFIG_CHANGED"))

        click: (device, config, row_el) =>
            # row_el is the monitoring check for mon-mode views
            defer = $q.defer()
            meta_device = @md_lut[device.idx]
            @pending.clicked.push([device.idx, meta_device.idx, config.idx, row_el.idx])
            # interpret
            # build config streams, key is config idx
            conf_stream = {}
            for _entry in @pending.clicked
                [_dev_idx, _meta_idx, _conf_idx, _el_idx] = _entry
                if _conf_idx not of conf_stream
                    conf_stream[_conf_idx] = []
                _cs = conf_stream[_conf_idx]
                if _dev_idx == _meta_idx
                    _cs.push({type: "m", idx: _meta_idx})
                else
                    _cs.push({type: "d", idx: _dev_idx, element: _el_idx})

            @pc_stream = conf_stream
            # console.log @pc_stream
            @check_pending()
            @link()
            defer.resolve("done")
            return defer.promise

        check_pending: () =>
            if @pending.clicked.length or @pending.removed.length
                @any_pending = true
            else
                @any_pending = false

        remove_pending: () =>
            @pending.clicked.length = 0
            @pending.removed.length = 0
            @pc_stream = {}
            @check_pending()
            @link()

        commit_changes: () =>
            defer = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.CONFIG_ALTER_CONFIG
                    data: {
                        mode: @mode
                        stream_data: angular.toJson(
                            (
                                {
                                    meta_pk: _meta_idx
                                    dev_pk: _dev_idx
                                    conf_pk: _conf_idx
                                    element_pk: _element_idx
                                }
                            ) for [_dev_idx, _meta_idx, _conf_idx, _element_idx] in @pending.clicked
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
                    $(xml).find("changeset > mon_check_command").each (idx, mc_entry) =>
                        _idx = parseInt($(mc_entry).attr("pk"))
                        mc = @config_tree.mon_basic_tree.mon_check_command_lut[_idx]
                        mc.exclude_devices.length = 0
                        $(mc_entry).find("exclude").each (idx, exc_entry) =>
                            # add exclude entries
                            exc_entry = $(exc_entry)
                            mc.exclude_devices.push(parseInt(exc_entry.attr("dev_idx")))
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
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal", "icswAccessLevelService",
    "icswTools", "ICSW_URLS", "$timeout", "icswDeviceTreeService", "blockUI",
    "icswConfigTreeService", "icswDeviceConfigHelper",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal, icswAccessLevelService,
    icswTools, ICSW_URLS, $timeout, icswDeviceTreeService, blockUI,
    icswConfigTreeService, icswDeviceConfigHelper,
) ->
    icswAccessLevelService.install($scope)
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
    "$rootScope", "$window",
(
    $q, blockUI, icswConfigMonCheckCommandListService, icswMonitoringBasicTreeService,
    $rootScope, $window,
)->
    {table, thead, div, tr, span, th, td, tbody, button, tbody} = React.DOM
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
                    _title_str = re.$$info_str
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
                _conf_grouping = []
                _last_idx = 0
                _mark_header = false
                create_groupinfo = false
                colspan = 1
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
                        colspan = if (@props.configHelper.mode !in ["gen", "srv"] &&
                            _conf.$$_dc_num_mcs? &&
                            _conf.$$_dc_num_mcs > 1) then _conf.$$_dc_num_mcs
                            else 1
                        if colspan > 1
                            create_groupinfo = true
                        groupstart = true
                    else
                        groupstart = false

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
                    if groupstart
                        _conf_grouping.push(
                            th(
                                {
                                    key: "grp-#{row_el.idx}"
                                    colSpan: colspan
                                    className: "group-indicator"
                                }
                            )
                        )
                        _conf_infos.push(
                            th(
                                {
                                    key: "info-#{row_el.idx}"
                                    colSpan: colspan
                                    # className: ["text-center", if _mark_header then "bg-success" else "bg-warning"].join(" ")
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
                if create_groupinfo
                    groupindicator = tr(
                        {
                        key: "groupindicator"
                        }
                        th({key: "g0", colSpan: 3})
                        _conf_grouping
                    )
                else
                    groupindicator = null
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
                    groupindicator
                    tr(
                        {key: "info"}
                        th({key: "t0"}, "Type")
                        th({key: "t1"}, "Local")
                        th({key: "t2"}, "Meta")
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
                return {focus: false, x: 0, y: 0}
            render: () ->
                _el = @props.rowElement
                if @props.configHelper.mode in ["gen", "srv"]
                    _conf = _el
                    _info_str = _el.$$info_str
                else
                    _conf = _el.$$config
                    _info_str = "#{_el.description} (#{_el.name})"
                [_class, _icon] = @props.configHelper.get_td_class_and_icon(_el, _conf, @props.device)
                if @state.focus
                    _class = "#{_class} bg-primary"
                if @props.configHelper.mode in ["mon"]
                    # overlay
                    _overlay = div(
                        {
                            key: "overlay"
                            display: "block"
                            className: "panel panel-default svg-tooltip"
                        }
                        div(
                            {
                                key: "heading"
                                className: "panel-heading"
                            }
                            _info_str
                        )
                        table(
                            {
                                key: "table"
                                className: "table table-striped table-condensed"
                            }
                            tbody(
                                {
                                    key: "tbody"
                                }
                                tr(
                                    {
                                        key: "first"
                                    }
                                    td(
                                        {
                                            key: "td0"
                                        }
                                        _el.$$command_str
                                    )
                                )
                            )
                        )
                    )
                    _title_str = null
                else
                    _overlay = null
                    _title_str = _info_str
                showtooltip = (event) =>
                    @setState({focus: true})
                    @props.focusCallback(_el, _conf, @props.device, true)
                    @props.configHelper.tooltip.show(_overlay)
                return td(
                    {
                        className: "text-center #{_class}"
                        onClick: (event) =>
                            if @props.configHelper.click_allowed(@props.device, _conf)
                                blockUI.start()
                                @props.configHelper.click(@props.device, _conf, _el).then(
                                    (ok) ->
                                        blockUI.stop()
                                )
                        onMouseEnter: showtooltip
                        onMouseMove: @props.configHelper.tooltip.pos
                        onMouseLeave: (event) =>
                            @props.configHelper.tooltip.hide()
                            @setState({focus: false})
                            @props.focusCallback(_el, _conf, @props.device, false)
                        title: _title_str
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
                if @props.configHelper.render_count != @state.counter or @props.configHelper.linedraw_dict[@props.device.idx] != @state.line_counter
                    @setState(
                        {
                            counter: @props.configHelper.render_count
                            line_counter: @props.configHelper.linedraw_dict[@props.device.idx]
                        }
                    )
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
            focus_cb = (row_el, conf, device, state) =>
                # @state.configHelper.clear_
                if state
                    @props.configHelper.set_focus(row_el, conf, device)
                    @setState({focus_el: conf.idx})
                else
                    if @state.focus_el
                        @props.configHelper.clear_focus()
                        @setState({focus_el: 0})

            if not @props.configHelper.devices.length
                return null

            table(
                {
                    key: "top"
                    className: "table rotateheaders table-condensed table-hover colhover"
                    style: {width: "auto", overflowX: "auto", display: "block", borderCollapse: "separate"}
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
]).directive('icswAssignTooltipContainer',
[
    "$window",
(
    $window
) ->
    return {
        restrict: "EA"
        scope: {
            helper: "=icswConfigHelper"
        }
        link: (scope, element, attrs) ->
            struct =
                divlayer: undefined

            struct.show = (content) ->
                if content?
                    _element = ReactDOM.render(
                        React.createElement(
                            React.createClass(
                                render: () -> content
                            )
                        )
                        element[0]
                    )
                    struct.divlayer = element.children().first()

            struct.pos = (event) ->
                if struct.divlayer?
                    t_os = 10  # Tooltip offset
                    top_scroll = $window.innerHeight - event.clientY - struct.divlayer[0].offsetHeight - t_os > 0
                    top_offset = if top_scroll then t_os else (struct.divlayer[0].offsetHeight + t_os) * -1
                    left_scroll = $window.innerWidth - event.clientX - struct.divlayer[0].offsetWidth - t_os > 0
                    left_offset = if left_scroll then t_os else (struct.divlayer[0].offsetWidth + t_os) * -1

                    struct.divlayer.css('left', "#{event.clientX + left_offset}px")
                    struct.divlayer.css('top', "#{event.clientY + top_offset}px")

            struct.hide = () ->
                if struct.divlayer?
                    struct.divlayer.css('left', "-10000px")
                    struct.divlayer.css('top', "-10000px")
                    struct.divlayer = undefined

             scope.helper.tooltip = struct
    }

])
