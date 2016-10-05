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
    "icsw.livestatus.comp.info",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegsterProvider) ->
    icswLivestatusPipeRegsterProvider.add("icswLivestatusInfoDisplay", true)
]).service("icswLivestatusInfoDisplay",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "icswMonitoringResult", "$timeout",
(
    $q, $rootScope, icswMonLivestatusPipeBase, icswMonitoringResult, $timeout,
) ->
    running_id = 0
    class icswLivestatusInfoDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusInfoDisplay", true, false)
            @set_template(
                '<icsw-livestatus-info-display icsw-connect-element="con_element"></icsw-livestatus-info-display>'
                "Info"
                4
                4
            )
            @new_data_notifier = $q.defer()

        new_data_received: (data) =>
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject(reject)

]).factory("icswLivestatusInfoDisplayReact",
[
    "$q", "icswLivestatusCircleInfoReact",
(
    $q, icswLivestatusCircleInfoReact,
) ->
    # display of livestatus filter
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span, table, tr, td, tbody} = React.DOM

    return React.createClass(
        propTypes: {
            monitoring_data: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                display_iter: 0
            }

        render: () ->
            _md = @props.monitoring_data
            _md.build_luts()
            return div(
                {
                    key: "top"
                    style: { marginTop: "10px" }
                }
                React.createElement(
                    icswLivestatusCircleInfoReact
                    {
                        data: _md.service_circle_data
                        title: "#{_md.services.length} Services"
                        titleSize: 14
                        className: "col-sm-6"
                        focusMode: "simple"
                        showInfo: true
                        showDetails: true
                    }
                )
                React.createElement(
                    icswLivestatusCircleInfoReact
                    {
                        data: _md.device_circle_data
                        title: "#{_md.hosts.length} Devices"
                        titleSize: 14
                        className: "col-sm-6"
                        showInfo: true
                        showDetails: true
                    }
                )
            )
    )
]).directive("icswLivestatusInfoDisplay",
[
    "$q", "icswLivestatusInfoDisplayReact",
(
    $q, icswLivestatusInfoDisplayReact,
) ->
    return  {
        restrict: "EA"
        replace: true
        scope:
            con_element: "=icswConnectElement"
        link: (scope, element, attr) ->
            _render = (data) ->
                ReactDOM.render(
                    React.createElement(
                        icswLivestatusInfoDisplayReact
                        {
                            monitoring_data: data
                        }
                    )
                    element[0]
                )
            scope.con_element.new_data_notifier.promise.then(
                (resolved) ->
                (rejected) ->
                (data) ->
                    _render(data)
            )
    }

])