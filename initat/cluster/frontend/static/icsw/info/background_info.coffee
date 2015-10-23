# Copyright (C) 2012-2015 init.at
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

DT_FORM = "dd, D. MMM YYYY HH:mm:ss"

background_job_info_module = angular.module(
    "icsw.info.background",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).service("icswBackgroundInfoRestService", ["$q", "Restangular", "icswCachingCall", "ICSW_URLS", ($q, Restangular, icswCachingCall, ICSW_URLS) ->
    _bi_info = []
    load_data = (client) ->
        _defer = $q.defer()
        _wait_list = [icswCachingCall.fetch(client, ICSW_URLS.REST_BACKGROUND_JOB_LIST, {}, [])]
        $q.all(_wait_list).then((data) ->
            _bi_info = data[0]
            _defer.resolve(_bi_info)
        )
        return _defer
    return {
        "load": (client) ->
            return load_data(client).promise
    }

]).service("icswBackgroundInfoListService", ["icswBackgroundInfoRestService", "$q", (icswBackgroundInfoRestService, $q) ->
    lines = $q.defer()
    icswBackgroundInfoRestService.load("bis").then((data) ->
        lines.resolve(data)
    )
    return {
        "load_promise": lines.promise
    }

]).directive("icswBackgroundJobInfoTable", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.background.job.info.table")
    }
]).factory("icswBackgroundJobFactory",
    [() ->
        {tr, td, strong, tbody} = React.DOM
        get_line_class = (job) ->
            if job.result == 0
                return ""
            else if job.result == 1
                return "warning"
            else
                return "danger"
        get_result_str = (job) ->
            return {
                0: "OK"
                1: "Warn"
                2: "Error"
                3: "Critical"
                4: "Unknown"
            }[job.result]
        get_diff_time = (dt) ->
            if dt
                return moment(dt).fromNow()
            else
                return "???"
        get_time = (dt) ->
            if dt
                return moment(dt).format(DT_FORM)
            else
                return "---"
        job_line = React.createClass(
            render: () ->
                return tr(
                    {key: @props.idx, className: get_line_class(@props)}
                    [
                        td(
                            {key: "td0"}
                            strong(
                                {}
                                @props.command
                            )
                        )
                        td({key: "res"}, get_result_str(@props))
                        td({key: "command", title: @props.command_xml}, @props.command_xml.substring(0, 10))
                        td({key: "date"}, get_time(@props.date) + " (" + get_diff_time(@props.date) + ")")
                        td({key: "user"}, @props.user_name)
                        td({key: "state"}, @props.state)
                        td({key: "init"}, @props.initiator_name)
                        td({key: "nums"}, @props.num_servers or "-")
                        td({key: "numo"}, @props.num_objects or "-")
                        td({key: "cause"}, @props.cause)
                        td({key: "until"}, get_time(@props.valid_until))
                    ]
                )
        )
        return job_line
]).directive("icswBackgroundJobLine", ["$templateCache", "icswBackgroundJobFactory", ($templateCache, icswBackgroundJobFactory) ->
    return {
        restrict: "EA"
        scope:
            line: "="
        link: (scope, el, attrs) ->
            ReactDOM.render(
                React.createElement(icswBackgroundJobFactory, scope.line)
                # FIXME, the following line is just a temporary hack until we can render whole tables via reactjs
                el.parent()[0]
            )
            scope._runtime = (diff) ->
                if diff
                    # seconds
                    return "#{diff} s"
                else
                    return "< 1s"
    }
])
