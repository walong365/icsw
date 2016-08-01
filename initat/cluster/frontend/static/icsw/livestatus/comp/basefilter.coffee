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

# livestatus basefilter

angular.module(
    "icsw.livestatus.comp.basefilter",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegsterProvider) ->
    icswLivestatusPipeRegsterProvider.add("icswLivestatusFilterService", true)
]).service("icswLivestatusFilterService",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "icswMonitoringResult", "$timeout",
(
    $q, $rootScope, icswMonLivestatusPipeBase, icswMonitoringResult, $timeout,
) ->
    running_id = 0
    class icswLivestatusFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusFilter", true, true)
            @set_template(
                '<icsw-livestatus-filter-display icsw-livestatus-filter="con_element"></icsw-livestatus-filter-display>'
                "BaseFilter"
                4
                1
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
                @new_data_received(@_latest_data)

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
                [0, "O", true, "show OK states", "btn-success"]
                [1, "W", true, "show warning states", "btn-warning"]
                [2, "C", true, "show critical states", "btn-danger"]
                [3, "U", true, "show unknown states", "btn-danger"]
                [5, "p", true, "show pending states", "btn-primary"]
            ]
            @service_state_lut = {}

            # possibel service type states
            @service_type_list = [
                [0, "S", true, "show soft states", "btn-primary"]
                [1, "H", true, "show hard states", "btn-primary"]
            ]
            @service_type_lut = {}

            # possible host states
            @host_state_list = [
                [0, "U", true, "show Up states", "btn-success"]
                [1, "D", true, "show Down states", "btn-warning"]
                [2, "?", true, "show unreachable states", "btn-danger"]
                [4, "M", true, "show unmonitored devs", "btn-primary"]
                [5, "p", true, "show pending devs", "btn-primary"]
            ]
            @host_state_lut = {}

            # possibel host type states
            @host_type_list = [
                [0, "S", true, "show soft states", "btn-primary"]
                [1, "H", true, "show hard states", "btn-primary"]
            ]
            @host_type_lut = {}

            # host / service filters are linke
            @linked = false

            # default values for service states
            @service_states = {}
            for entry in @service_state_list
                @service_state_lut[entry[0]] = entry
                @service_state_lut[entry[1]] = entry
                @service_states[entry[0]] = entry[2]

            # default values for host states
            @host_states = {}
            for entry in @host_state_list
                @host_state_lut[entry[0]] = entry
                @host_state_lut[entry[1]] = entry
                @host_states[entry[0]] = entry[2]
                
            # default values for service types
            @service_types = {}
            for entry in @service_type_list
                @service_type_lut[entry[0]] = entry
                @service_type_lut[entry[1]] = entry
                @service_types[entry[0]] = entry[2]

            # default values for service types
            @host_types = {}
            for entry in @host_type_list
                @host_type_lut[entry[0]] = entry
                @host_type_lut[entry[1]] = entry
                @host_types[entry[0]] = entry[2]

            @react_notifier = $q.defer()
            @change_notifier = $q.defer()
            # category filter settings
            @cat_filter_installed = false

        restore_settings: (settings) =>
            # restore settings
            [_ss, _hs, _st, _ht, _linked] = settings.split(";")
            @linked = if _linked == "l" then true else false
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
                for key in _field.split(":")
                    try
                        _dict[_lut[key][0]] = true
                    catch err
                        console.error err

        toggle_link_state: () =>
            @linked = !@linked
            @_settings_changed()

        toggle_service_state: (code) =>
            _srvc_idx = @service_state_lut[code][0]
            @service_states[_srvc_idx] = !@service_states[_srvc_idx]
            @_settings_changed()

        toggle_host_state: (code) =>
            _host_idx = @host_state_lut[code][0]
            @host_states[_host_idx] = !@host_states[_host_idx]
            @_settings_changed()

        toggle_service_type: (code) =>
            _type_idx = @service_type_lut[code][0]
            @service_types[_type_idx] = !@service_types[_type_idx]
            @_settings_changed()

        toggle_host_type: (code) =>
            _type_idx = @host_type_lut[code][0]
            @host_types[_type_idx] = !@host_types[_type_idx]
            @_settings_changed()

        # get state strings for ReactJS, a little hack ...
        _get_service_state_str: () =>
            return (entry[1] for entry in @service_state_list when @service_states[entry[0]]).join(":")

        _get_host_state_str: () =>
            return (entry[1] for entry in @host_state_list when @host_states[entry[0]]).join(":")
            
        _get_service_type_str: () =>
            return (entry[1] for entry in @service_type_list when @service_types[entry[0]]).join(":")

        _get_host_type_str: () =>
            return (entry[1] for entry in @host_type_list when @host_types[entry[0]]).join(":")

        _get_linked_str: () =>
            return if @linked then "l" else "ul"

        get_filter_state_str: () ->
            return [
                @_get_service_state_str()
                @_get_host_state_str()
                @_get_service_type_str()
                @_get_host_type_str()
                @_get_linked_str()
            ].join(";")

        _settings_changed: () ->
            @pipeline_settings_changed(@get_filter_state_str())

        stop_notifying: () ->
            @change_notifier.reject("stop")

]).factory("icswLivestatusFilterReactDisplay",
[
    "$q", "icswLivestatusCircleInfoReact",
(
    $q, icswLivestatusCircleInfoReact,
) ->
    # display of livestatus filter
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span, table, tr, td, tbody, span, button} = React.DOM

    return React.createClass(
        propTypes: {
            livestatus_filter: React.PropTypes.object
            # filter_changed_cb: React.PropTypes.func
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

        render: () ->

            _filter_changed = () =>
                @props.livestatus_filter.filter_changed()

            _active_class = "svg_active"
            _inact_class = "svg_inactive"
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
            _service_buttons = []
            for entry in _lf.service_state_list
                _service_buttons.push(
                    input(
                        {
                            key: "srvc.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.service_states[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                # _lf.toggle_md(event.target_value)
                                _lf.toggle_service_state(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _host_buttons = []
            for entry in _lf.host_state_list
                _host_buttons.push(
                    input(
                        {
                            key: "host.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.host_states[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                _lf.toggle_host_state(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _s_type_buttons = []
            for entry in _lf.service_type_list
                _s_type_buttons.push(
                    input(
                        {
                            key: "stype.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.service_types[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                _lf.toggle_service_type(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )

            _h_type_buttons = []
            for entry in _lf.host_type_list
                _h_type_buttons.push(
                    input(
                        {
                            key: "stype.#{entry[1]}"
                            type: "button"
                            className: "btn btn-xs " + if _lf.host_types[entry[0]] then entry[4] else "btn-default"
                            value: entry[1]
                            title: entry[3]
                            onClick: (event) =>
                                _lf.toggle_host_type(event.target.value)
                                # force redraw
                                @setState({filter_state_str: _lf.get_filter_state_str()})
                                _filter_changed()
                        }
                    )
                )
            _lock_class = if _lf.linked then "fa-lock" else "fa-unlock"
            return div(
                {key: "top"}
                table(
                    {key: "mt", className: "table table-condensed", style: {"width": "auto"}}
                    tbody(
                        {key: "body"}
                        tr(
                            {key: "l0"}
                            td(
                                {key: "ltd", rowSpan: "2"}
                                button(
                                    {
                                        type: "button"
                                        className: "btn btn-default"
                                        key: "linkbut"
                                        onClick: (event) =>
                                            _lf.toggle_link_state()
                                            @setState({filter_state_str: _lf.get_filter_state_str()})
                                            _filter_changed()
                                    }
                                    span(
                                        {
                                            key: "linkedspan"
                                            className: "fa fa-4x #{_lock_class} fa-fw"
                                        }
                                    )
                                )
                            )
                            td(
                                {key: "t0"}
                                "Host"
                            )
                            td(
                                {key: "t1"}
                                div(
                                    {key: "t1g", className: "btn-group"}
                                    _host_buttons
                                )
                            )
                            td(
                                {key: "t2"}
                                div(
                                    {key: "t2g", className: "btn-group"}
                                    _h_type_buttons
                                )
                            )
                            td(
                                {key: "t4", rowSpan: "2"}
                                React.createElement(
                                    icswLivestatusCircleInfoReact
                                    {
                                        size: 44
                                        data: _host_data
                                        text: _host_text
                                    }
                                )
                            )
                            td(
                                {key: "t5", rowSpan: "2"}
                                React.createElement(
                                    icswLivestatusCircleInfoReact
                                    {
                                        size: 44
                                        data: _service_data
                                        text: _service_text
                                    }
                                )
                            )
                        )
                        tr(
                            {key: "l1"}
                            td(
                                {key: "t0"}
                                "Service"
                            )
                            td(
                                {key: "t1"}
                                div(
                                    {key: "t1g", className: "btn-group"}
                                    _service_buttons
                                )
                            )
                            td(
                                {key: "t2"}
                                div(
                                    {key: "t2g", className: "btn-group"}
                                    _s_type_buttons
                                )
                            )
                        )
                    )
                )

            )
    )
]).directive("icswLivestatusFilterDisplay",
[
    "$q", "icswLivestatusFilterReactDisplay",
(
    $q, icswLivestatusFilterReactDisplay,
) ->
    return  {
        restrict: "EA"
        replace: true
        scope:
            filter: "=icswLivestatusFilter"
        link: (scope, element, attr) ->
            ReactDOM.render(
                React.createElement(
                    icswLivestatusFilterReactDisplay
                    {
                        livestatus_filter: scope.filter
                    }
                )
                element[0]
            )
    }

])