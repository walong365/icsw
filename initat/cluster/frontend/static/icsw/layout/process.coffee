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

menu_module = angular.module(
    "icsw.layout.process",
    [
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection", "icsw.user",
    ]
).service("icswProcessService",
[
    "$q",
(
    $q,
) ->
    struct = {
        active_process: null
    }
    return {
        get_struct: () ->
            return struct
    }
]).factory("icswProcessOverviewReact",
[
    "icswUserService", "icswOverallStyle", "icswProcessService",
(
    icswUserService, icswOverallStyle, icswProcessService,
) ->
    {ul, li, a, span, h4, div, p, strong, h3, i, hr, button} = React.DOM
    return React.createClass(
        # propTypes:
        #    side: React.PropTypes.string

        displayName: "ProcessOverview"

        getInitialState: () ->
            return {
                counter: 0
                struct: null
            }

        componentWillMount: () ->
            @setState({struct: icswProcessService.get_struct()})

        state_from_struct: () ->
            @setState(
                {

                }
            )
            console.log "sfs"

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        render: () ->
            console.log "RR", @state
            # _menu_struct = icswRouteHelper.get_struct()
            # menus = (entry for entry in _menu_struct.menu_node.entries when entry.data.side == @props.side)
            _el_list = []
            _proc_active = if @state.struct.active_process then true else false
            if _proc_active
                _el_list.push(
                    button(
                        {
                            key: "bwb"
                            type: "button"
                            className: "btn btn-xs btn-default"
                        }
                        span(
                            {
                                className: "glyphicon glyphicon-triangle-left"
                            }
                        )
                    )
                )
                _el_list.push("Process")
                _el_list.push(
                    button(
                        {
                            key: "bwf"
                            type: "button"
                            className: "btn btn-xs btn-default"
                        }
                        span(
                            {
                                className: "glyphicon glyphicon-triangle-right"
                            }
                        )
                    )
                )
                _a_style = {padding: "12px"}
            else
                _el_list.push(
                    span(
                        {
                            key: "np"
                            className: "label label-default cursorpointer"
                            title: "No process active"
                            onClick: (event) ->
                                console.log "cl"
                        }
                        "NPA"
                    )
                )
                _a_style = {}
            _res = li(
                {}
                a(
                    {
                        style: _a_style
                    }
                    _el_list
                )
            )
            return _res
    )
])
