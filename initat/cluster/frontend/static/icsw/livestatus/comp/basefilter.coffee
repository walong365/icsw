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

# livestatus basefilter

angular.module(
    "icsw.livestatus.comp.basefilter",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusFilterService", true)
]).service("icswLivestatusFilterService",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "icswMonitoringResult", "$timeout",
    "icswSaltMonitoringResultService",
(
    $q, $rootScope, icswMonLivestatusPipeBase, icswMonitoringResult, $timeout,
    icswSaltMonitoringResultService,
) ->
    struct = icswSaltMonitoringResultService.get_struct()

    class StateEntry
        constructor: (@type, @idx, @short_code, @default_sel, @help_str, @btn_class) ->
            if @type == "dev"
                @data = struct.device_lut[@idx]
            else
                @data = struct.service_lut[@idx]

    class StateTypeEntry
        constructor: (@type, @idx, @short_code, @default_sel, @help_str, @btn_class) ->
            @data = struct.state_lut[@idx]

    running_id = 0
    class icswLivestatusFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusFilterService", true, true)
            @set_template(
                '<icsw-livestatus-filter-display icsw-livestatus-filter="con_element"></icsw-livestatus-filter-display>'
                "Base Filter"
                3
                2
            )
            running_id++
            @id = running_id
            @_latest_data = undefined
            @__dp_async_emit = true
            # emit data
            @_emit_data = new icswMonitoringResult()
            @_local_init()
            @set_async_emit_data(@_emit_data)

        filter_changed: () ->
            # callback from React
            if @_latest_data?
                @new_data_received_cached(@_latest_data)

        new_data_received: (data) =>
            @_latest_data = data
            @n_hosts = data.hosts.length
            @n_services = data.services.length
            @categories = data.categories

            @_emit_data.apply_base_filter(@, @_latest_data)
            @f_hosts = @_emit_data.hosts.length
            @f_services = @_emit_data.services.length
            @react_notifier.notify()
            # make it asynchronous
            $timeout(
                () =>
                    @_emit_data.notify()
                0
            )
            return null

        pipeline_reject_called: (reject) ->
            # ignore, stop processing

        _local_init: () =>
            # console.log "new LivestatusFilter with id #{@id}"
            @categories = []
            # number of entries
            @n_hosts = 0
            @n_services = 0
            # filtered entries
            @f_hosts = 0
            @f_services = 0
            # possible service states
            @service_state_list = [
                new StateEntry("srv", 0, "O", true, "show OK States", "btn-success")
                new StateEntry("srv", 1, "W", true, "show Warning States", "btn-warning")
                new StateEntry("srv", 2, "C", true, "show Critical States", "btn-danger")
                new StateEntry("srv", 3, "U", true, "show Unknown States", "btn-danger")
                new StateEntry("srv", 5, "p", true, "show Pending States", "btn-primary")
            ]
            @service_state_lut = {}

            # possibel service type states
            @service_type_list = [
                new StateTypeEntry("srv", 0, "S", true, "show Soft States", "btn-primary")
                new StateTypeEntry("srv", 1, "H", true, "show Hard States", "btn-primary")
            ]
            @service_type_lut = {}

            # possible host states
            @host_state_list = [
                new StateEntry("dev", 0, "U", true, "show Up States", "btn-success")
                new StateEntry("dev", 1, "D", true, "show Down States", "btn-warning")
                new StateEntry("dev", 2, "?", true, "show Unreachable States", "btn-danger")
                new StateEntry("dev", 4, "M", true, "show Unmonitored Devices", "btn-primary")
                new StateEntry("dev", 5, "p", true, "show Pending Devices", "btn-primary")
            ]
            @host_state_lut = {}

            # possibel host type states
            @host_type_list = [
                new StateTypeEntry("dev", 0, "S", true, "show Soft States", "btn-primary")
                new StateTypeEntry("dev", 1, "H", true, "show Hard States", "btn-primary")
            ]
            @host_type_lut = {}

            # host / service filters are linked
            @linked = false
            # show active host results
            @active_host_results = true
            # show active service results
            @active_service_results = true
            # show passive host results
            @passive_host_results = true
            # show passive host results
            @passive_service_results = true

            # default values for service states
            @service_states = {}
            for entry in @service_state_list
                @service_state_lut[entry.idx] = entry
                @service_state_lut[entry.short_code] = entry
                @service_states[entry.idx] = entry.default_sel

            # default values for host states
            @host_states = {}
            for entry in @host_state_list
                @host_state_lut[entry.idx] = entry
                @host_state_lut[entry.short_code] = entry
                @host_states[entry.idx] = entry.default_sel
                
            # default values for service types
            @service_types = {}
            for entry in @service_type_list
                @service_type_lut[entry.idx] = entry
                @service_type_lut[entry.short_code] = entry
                @service_types[entry.idx] = entry.default_sel

            # default values for service types
            @host_types = {}
            for entry in @host_type_list
                @host_type_lut[entry.idx] = entry
                @host_type_lut[entry.short_code] = entry
                @host_types[entry.idx] = entry.default_sel

            @react_notifier = $q.defer()
            @change_notifier = $q.defer()
            # category filter settings
            @cat_filter_installed = false

        restore_settings: (settings) =>
            # console.log "RS", settings
            # restore settings
            [_ss, _hs, _st, _ht, _flags] = settings.split(";")
            if _flags.length == 1
                # old format
                @linked = if _flags == "l" then true else false
                @active_host_results = true
                @active_service_results = true
                @passive_host_results = true
                @passive_service_results = true
            else
                _flags = _flags.split(":")
                @linked = if _flags[0] == "l" then true else false
                if _flags.length == 3
                    # old format
                    @active_host_results = if _flags[1] == "ar" then true else false
                    @passive_host_results = if _flags[2] == "pr" then true else false
                    @active_service_results = @active_host_results
                    @passive_service_results = @passive_host_results
                else
                    @active_host_results = if _flags[1] == "ahr" then true else false
                    @passive_host_results = if _flags[2] == "phr" then true else false
                    @active_service_results = if _flags[3] == "asr" then true else false
                    @passive_service_results = if _flags[4] == "psr" then true else false

            for [_field, _attr_prefix] in [
                [_ss, "service_state"]
                [_hs, "host_state"]
                [_st, "service_type"]
                [_ht, "host_type"]
            ]
                _dict = @["#{_attr_prefix}s"]
                _lut = @["#{_attr_prefix}_lut"]
                # clear all
                for key, value of _dict
                    _dict[key] = false
                # set referenced
                if _field
                    for key in _field.split(":")
                        try
                            _dict[_lut[key].idx] = true
                        catch err
                            console.error "settings=#{settings}, key=#{key}, err=#{err}"

        toggle_link_state: () =>
            @linked = !@linked
            @_settings_changed()

        toggle_active_host_results: () =>
            @active_host_results = !@active_host_results
            @_settings_changed()

        toggle_passive_host_results: () =>
            @passive_host_results = !@passive_host_results
            @_settings_changed()

        toggle_active_service_results: () =>
            @active_service_results = !@active_service_results
            @_settings_changed()

        toggle_passive_service_results: () =>
            @passive_service_results = !@passive_service_results
            @_settings_changed()

        toggle_service_state: (code) =>
            _srvc_idx = @service_state_lut[code].idx
            @service_states[_srvc_idx] = !@service_states[_srvc_idx]
            @_settings_changed()

        toggle_host_state: (code) =>
            _host_idx = @host_state_lut[code].idx
            @host_states[_host_idx] = !@host_states[_host_idx]
            @_settings_changed()

        toggle_service_type: (code) =>
            _type_idx = @service_type_lut[code].idx
            @service_types[_type_idx] = !@service_types[_type_idx]
            @_settings_changed()

        toggle_host_type: (code) =>
            _type_idx = @host_type_lut[code].idx
            @host_types[_type_idx] = !@host_types[_type_idx]
            @_settings_changed()

        # get state strings for ReactJS, a little hack ...
        _get_service_state_str: () =>
            return (entry.short_code for entry in @service_state_list when @service_states[entry.idx]).join(":")

        _get_host_state_str: () =>
            return (entry.short_code for entry in @host_state_list when @host_states[entry.idx]).join(":")
            
        _get_service_type_str: () =>
            return (entry.short_code for entry in @service_type_list when @service_types[entry.idx]).join(":")

        _get_host_type_str: () =>
            return (entry.short_code for entry in @host_type_list when @host_types[entry.idx]).join(":")

        _get_flags_str: () =>
            return [
                if @linked then "l" else "ul"
                if @active_host_results then "ahr" else "hr"
                if @passive_host_results then "phr" else "hr"
                if @active_service_results then "asr" else "sr"
                if @passive_service_results then "psr" else "sr"
            ].join(":")

        get_filter_state_str: () ->
            return [
                @_get_service_state_str()
                @_get_host_state_str()
                @_get_service_type_str()
                @_get_host_type_str()
                @_get_flags_str()
            ].join(";")

        _settings_changed: () ->
            # console.log "SC", @get_filter_state_str()
            @pipeline_settings_changed(@get_filter_state_str())

        stop_notifying: () ->
            @change_notifier.reject("stop")

]).factory("icswLivestatusFilterReactDisplay",
[
    "$q", "icswLivestatusCircleInfoReact", "icswDeviceLivestatusFunctions", "icswSaltMonitoringResultService",
(
    $q, icswLivestatusCircleInfoReact, icswDeviceLivestatusFunctions, icswSaltMonitoringResultService,
) ->
    # display of livestatus filter
    {span, rect, title, span, svg, path, g, text, div} = React.DOM

    ap_filter = React.createFactory(
        React.createClass(
            propTypes: {
                for_active: React.PropTypes.bool
                enabled: React.PropTypes.bool
                change_callback: React.PropTypes.func
                update_filter: React.PropTypes.func
                offset_x: React.PropTypes.number
                offset_y: React.PropTypes.number
                object_name: React.PropTypes.string
            }

            render: () ->
                if @props.for_active
                    _str = "active"
                else
                    _str = "passive"

                return g(
                    {}
                    rect(
                        {
                            key: "activerect"
                            x: @props.offset_x - 10 # -21
                            y: -18
                            width: 20
                            height: 20
                            rx: 2
                            ry: 2
                            className: "svg-box"
                            style: {fill: if @props.enabled then "#ffffff" else "#888888"}
                        }
                    )
                    text(
                        {
                            key: "linktexta"
                            x: @props.offset_x  # -11
                            y: -1
                            fontFamily: "fontAwesome"
                            className: "cursorpointer svg-box-content"
                            fontSize: "20px"
                            # alignmentBaseline: "middle"  # bad for browser/ os compat
                            textAnchor: "middle"
                            pointerEvents: "painted"
                            onClick: (event) =>
                                @props.change_callback()
                                @props.update_filter()
                        }
                        title(
                            {
                                key: "title.activetext"
                            }
                            if @props.for_active then "Show #{_str} #{@props.object_name} results" else "Show no #{_str} #{@props.object_name} results"
                        )
                        if @props.for_active then "\uf062" else "\uf063"
                    )
                )
        )
    )
    return React.createClass(
        propTypes: {
            livestatus_filter: React.PropTypes.object
            filter_changed_cb: React.PropTypes.func
        }
        getInitialState: () ->
            return {
                filter_state_str: @props.livestatus_filter.get_filter_state_str()
                display_iter: 0
            }

        componentWillMount: () ->
            # @umount_defer = $q.defer()
            @props.livestatus_filter.react_notifier.promise.then(
                () ->
                () ->
                    # will get called when the component unmounts
                (c) =>
                    @setState({display_iter: @state.display_iter + 1})
            )

        componentWillUnmount: () ->
            @props.livestatus_filter.stop_notifying()

        shouldComponentUpdate: (next_props, next_state) ->
            _redraw = false
            if next_state.display_iter != @state.display_iter
                _redraw = true
            else if next_state.filter_state_str != @state.filter_state_str
                _redraw = true
            return _redraw

        filter_set: () ->
            @setState({display_iter: @state.display_iter + 1})
            @props.livestatus_filter._settings_changed()
            @props.livestatus_filter.filter_changed()

        render: () ->
            _filter_changed = () =>
                @props.livestatus_filter.filter_changed()
                @props.filter_changed_cb()

            _update_filter = () =>
                @setState({filter_state_str: _lf.get_filter_state_str()})
                _filter_changed()
            _active_class = "svg-active"
            _inact_class = "svg-inactive"
            # console.log "r", @props.livestatus_filter
            _lf = @props.livestatus_filter
            if _lf.f_hosts != _lf.n_hosts
                _host_text = "#{_lf.f_hosts} / #{_lf.n_hosts}"
                _host_data = [
                    [_lf.f_hosts, _active_class, null]
                    [_lf.n_hosts - _lf.f_hosts, _inact_class, null]
                ]
            else
                _host_text = "#{_lf.n_hosts}"
                _host_data = [
                    [_lf.n_hosts, _active_class, null]
                ] 
            if _lf.f_services != _lf.n_services
                _service_text = "#{_lf.f_services} / #{_lf.n_services}"
                _service_data = [
                    [_lf.f_services, _active_class, null]
                    [_lf.n_services - _lf.f_services, _inact_class, null]
                ]
            else
                _service_text = "#{_lf.n_services}"
                _service_data = [
                    [_lf.n_services, _active_class, null]
                ]

            _build_ring = (in_list, inner, outer, class_cb, click_cb) ->
                _rings = []
                _end_arc = 0
                _cur_size = 0
                _middle = (inner + outer) / 2.0
                _total = in_list.length
                _idx = 0
                for entry in in_list
                    _idx++
                    _start_arc = _end_arc
                    _prev_size = _cur_size
                    _cur_size++
                    _end_arc = Math.PI * 2.0 *_cur_size / _total #  - Math.PI * 0.5
                    _middle_arc = Math.PI * 2.0 * (_cur_size + _prev_size) / (2.0 * _total)
                    _middle_x = Math.cos(_middle_arc) * _middle
                    _middle_y = Math.sin(_middle_arc) * _middle
                    _rings.push(
                        path(
                            {
                                key: "seg.#{_idx}"
                                d: icswDeviceLivestatusFunctions.ring_segment_path(inner, outer, _start_arc, _end_arc)
                                className: class_cb(entry)
                                id: entry.short_code
                                onClick: (event) =>
                                    click_cb($(event.target).attr("id"))
                                    _filter_changed()
                            }
                            title(
                                {
                                    key: "seg.#{_idx}.title"
                                }
                                entry.help_str
                            )
                        )
                    )
                    _rings.push(
                        text(
                            {
                                key: "seg.#{_idx}.t"
                                transform: "translate(#{_middle_x}, #{_middle_y + 4})"
                                fontFamily: "fontAwesome"
                                className: "cursorpointer svg-filter-text"
                                pointerEvents: "none"
                                # alignmentBaseline: "middle"  # bad for browser/ os compat
                                textAnchor: "middle"
                            }
                            entry.data.iconCode
                        )
                    )
                return _rings

            # build rings
            _rads = [0, 20, 22, 42]
            _rings_0 = _build_ring(
                _lf.host_state_list
                _rads[2]
                _rads[3]
                (entry) =>
                    if _lf.host_states[entry.idx]
                        return "cursorpointer sb-lines #{entry.data.svgClassName}"
                    else
                        return "cursorpointer sb-lines svg-dev-unselected"
                (code) =>
                    _lf.toggle_host_state(code)
                    @setState({filter_state_str: _lf.get_filter_state_str()})
            )
            _rings_1 = _build_ring(
                _lf.host_type_list
                _rads[0]
                _rads[1]
                (entry) ->
                    if _lf.host_types[entry.idx]
                        return "cursorpointer sb-lines svg-sh-type"
                    else
                        return "cursorpointer sb-lines svg-dev-unselected"
                (code) =>
                    _lf.toggle_host_type(code)
                    @setState({filter_state_str: _lf.get_filter_state_str()})
            )
            _rings_2 = _build_ring(
                _lf.service_state_list
                _rads[2]
                _rads[3]
                (entry) =>
                    if _lf.service_states[entry.idx]
                        return "cursorpointer sb-lines #{entry.data.svgClassName}"
                    else
                        return "cursorpointer sb-lines svg-srv-unselected"
                (code) =>
                    _lf.toggle_service_state(code)
                    @setState({filter_state_str: _lf.get_filter_state_str()})
            )
            _rings_3 = _build_ring(
                _lf.service_type_list
                _rads[0]
                _rads[1]
                (entry) ->
                    if _lf.service_types[entry.idx]
                        return "cursorpointer sb-lines svg-sh-type"
                    else
                        return "cursorpointer sb-lines svg-srv-unselected"
                (code) =>
                    _lf.toggle_service_type(code)
                    @setState({filter_state_str: _lf.get_filter_state_str()})
            )
            _width = 220

            head_text_width = (in_str) ->
                return _.min([1.8 * 56 / (2 + in_str.length), 15])

            _height = 140
            # console.log "RENDER"
            return div(
                {
                    key: "top"
                }
                svg(
                    {
                        key: "top"
                        width: "98%"  # browser crap
                        fontFamily: "'Open-Sans', sans-serif"
                        fontSize: "10pt"
                        viewBox: "5 11 210 121"
                    }
                    [
                        g(
                            {
                                key: "link"
                                transform: "translate(#{_width / 2}, 80)"
                            }
                            [
                                rect(
                                    {
                                        key: "rlink"
                                        x: -100
                                        y: -50
                                        rx: 50
                                        ry: 50
                                        width: 200
                                        height: 100
                                        className: if _lf.linked then "svg-strokelocked" else "svg-strokeunlocked"
                                        style: {
                                            fill: "none",
                                            strokeWidth: "3px"
                                        }
                                    }

                                )
                                g(
                                    {
                                        key: "activepassivebutton"
                                        transform: "translate(0, 50)"
                                    }
                                    [
                                        ap_filter(
                                            {
                                                key: "active0"
                                                for_active: true
                                                object_name: "host"
                                                enabled: _lf.active_host_results
                                                change_callback: _lf.toggle_active_host_results
                                                update_filter: _update_filter
                                                offset_x: -92
                                            }
                                        )
                                        ap_filter(
                                            {
                                                key: "passive0"
                                                for_active: false
                                                object_name: "host"
                                                enabled: _lf.passive_host_results
                                                change_callback: _lf.toggle_passive_host_results
                                                update_filter: _update_filter
                                                offset_x: -70
                                            }
                                        )
                                        ap_filter(
                                            {
                                                key: "active1"
                                                for_active: true
                                                object_name: "service"
                                                enabled: _lf.active_service_results
                                                change_callback: _lf.toggle_active_service_results
                                                update_filter: _update_filter
                                                offset_x: 70
                                            }
                                        )
                                        ap_filter(
                                            {
                                                key: "passive1"
                                                for_active: false
                                                object_name: "service"
                                                enabled: _lf.passive_service_results
                                                change_callback: _lf.toggle_passive_service_results
                                                update_filter: _update_filter
                                                offset_x: 92
                                            }
                                        )
                                    ]
                                )
                                g(
                                    {
                                        key: "linkbutton"
                                        transform: "translate(0, -50)"
                                    }
                                    [
                                        rect(
                                            {
                                                key: "buttonrect"
                                                x: -15
                                                y: -15
                                                width: 30
                                                height: 30
                                                rx: 3
                                                ry: 3
                                                className: "svg-box"
                                            }
                                        )
                                        text(
                                            {
                                                key: "linktext"
                                                x: 0
                                                y: 13
                                                fontFamily: "fontAwesome"
                                                className: "cursorpointer svg-box-content"
                                                fontSize: "30px"
                                                # alignmentBaseline: "middle"  # bad for browser/ os compat
                                                textAnchor: "middle"
                                                pointerEvents: "painted"
                                                onClick: (event) =>
                                                    _lf.toggle_link_state()
                                                    @setState({filter_state_str: _lf.get_filter_state_str()})
                                                    _filter_changed()
                                            }
                                            title(
                                                {
                                                    key: "title.linktext"
                                                }
                                                if _lf.linked then "Unlink Devices and Services" else "Link Services to Devices"
                                            )
                                            if _lf.linked then "\uf023" else "\uf13e"
                                        )
                                    ]
                                )
                                g(
                                    {
                                        key: "hosts"
                                        transform: "translate(-50, 0)"
                                    }
                                    [
                                        g(
                                            {
                                                key: "gtext"
                                                transform: "translate(-10, -50)"
                                            }
                                            rect(
                                                {
                                                    key: "textrect"
                                                    x: -21
                                                    y: -9
                                                    width: 61
                                                    height: 16
                                                    className: "svg-box"
                                                }
                                            )
                                            text(
                                                {
                                                    key: "text"
                                                    y: 5
                                                    x: 10
                                                    className: "svg-filter-head-text"
                                                    style: {fontSize : head_text_width(_host_text)}
                                                }
                                                "#{_host_text}"
                                            )
                                        )
                                        _rings_0
                                        _rings_1
                                    ]
                                )
                                g(
                                    {
                                        key: "services"
                                        transform: "translate(50, 0)"
                                    }
                                    [
                                        g(
                                            {
                                                key: "gtext"
                                                transform: "translate(10, -50)"
                                            }
                                            rect(
                                                {
                                                    key: "textrect"
                                                    x: -40
                                                    y: -9
                                                    width: 61
                                                    height: 16
                                                    className: "svg-box"
                                                }
                                            )
                                            text(
                                                {
                                                    key: "text"
                                                    y: 5
                                                    x: -10
                                                    className: "svg-filter-head-text"
                                                    style: {fontSize : head_text_width(_service_text)}
                                                }
                                                "#{_service_text}"
                                            )
                                        )
                                        _rings_2
                                        _rings_3
                                    ]
                                )
                            ]
                        )
                    ]
                )
            )
    )
]).directive("icswLivestatusFilterDisplay",
[
    "$q", "icswLivestatusFilterReactDisplay", "$templateCache",
(
    $q, icswLivestatusFilterReactDisplay, $templateCache,
) ->
    class DefinedFilter
        constructor: (@id, @name, @filter_str) ->

    return  {
        restrict: "EA"
        replace: true
        scope:
            filter: "=icswLivestatusFilter"
        template: $templateCache.get("icsw.livestatus.filter.display")
        link: (scope, element, attr) ->
            # predefined filters
            scope.filter_list = [
                new DefinedFilter("c", "Custom", "")
                new DefinedFilter("a", "All Services and Hosts", "O:W:C:U:p;U:D:?:M:p;S:H;S:H;ul:ar:pr")
                new DefinedFilter("hd", "All Down and Problem hosts", "O:W:C:U:p;D:?:M:p;S:H;S:H;ul:ar:pr")
                new DefinedFilter("um", "All Unmonitored and Pending Hosts", "O:W:C:U:p;M:p;S:H;S:H;ul:ar:pr")
                new DefinedFilter("upp", "All Hard Problems on Up Hosts", "W:C:U:p;U;H;H;l:ar:pr")
            ]

            scope.filter_changed = () ->
                _cur_fs = scope.filter.get_filter_state_str()
                console.log "fs=", _cur_fs
                scope.struct.cur_filter = scope.filter_list[0]
                for entry in scope.filter_list
                    if entry.filter_str == _cur_fs
                        scope.struct.cur_filter = entry

            scope.struct = {
                cur_filter: scope.filter_list[0]
            }

            scope.filter_settings_changed = () ->
                if scope.struct.cur_filter.filter_str
                    scope.filter.restore_settings(scope.struct.cur_filter.filter_str)
                    new_rel.filter_set()

            new_rel = ReactDOM.render(
                React.createElement(
                    icswLivestatusFilterReactDisplay
                    {
                        livestatus_filter: scope.filter
                        filter_changed_cb: scope.filter_changed
                    }
                )
                $(element).find("div#svg")[0]
            )
            # console.log new_rel
    }

])
