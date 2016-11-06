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
    "icsw.system.background",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.backgroundinfo")
]).service("icswSystemBackgroundInfoRestService",
[
    "$q", "Restangular", "icswCachingCall", "ICSW_URLS",
(
    $q, Restangular, icswCachingCall, ICSW_URLS
) ->
    _bi_info = []
    load_data = (client) ->
        _defer = $q.defer()
        _wait_list = [icswCachingCall.fetch(client, ICSW_URLS.SESSION_BACKGROUND_JOBS)]
        $q.all(_wait_list).then((data) ->
            _bi_info = data[0]
            _defer.resolve(_bi_info)
        )
        return _defer
    return {
        load: (client) ->
            return load_data(client).promise
    }

]).service("icswSystemBackgroundInfoListService",
[
    "icswSystemBackgroundInfoRestService", "$q",
(
    icswSystemBackgroundInfoRestService, $q
) ->
    return {
        fetch: (scope) ->
            defer= $q.defer()
            icswSystemBackgroundInfoRestService.load(scope.$id).then(
                (data) ->
                    defer.resolve(data)
            )
            return defer.promise
    }

]).directive("icswSystemBackgroundJobInfoTable",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.system.background.job.info.table")
    }
]).factory("icswSystemBackgroundJobFactory",
[
    "$q",
(
    $q,
) ->
    {tr, td, strong} = React.DOM

    get_line_class = (job) ->
        if job.result == 0
            return ""
        else if job.result == 1
            return "warning"
        else
            return "danger"

    get_srv_reply_str = (srv_reply) ->
        # SRV_REPLY_STATE
        return {
            0: "OK"
            1: "Warn"
            2: "Error"
            3: "Critical"
            4: "Unknown"
        }[srv_reply]

    get_diff_time = (dt) ->
        if dt
            return moment(dt).fromNow()
        else
            return "???"
    get_time = (dt) ->
        if dt
            DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            return moment(dt).format(DT_FORM)
        else
            return "---"

    return React.createClass(
        render: () ->
            if @props.background_job_run_set.length
                _states = (
                    entry.state for entry in @props.background_job_run_set
                )
                details = (get_srv_reply_str(reply) for reply in _states)

                # console.log @props.state, @props.result
                # console.log _states
                # console.log @props.background_job_run_set
            else
                details = []

            return tr(
                {
                    key: @props.idx,
                    # className: get_line_class(@props)
                }
                [
                    td(
                        {key: "td0"}
                        strong(
                            {}
                            @props.command
                        )
                    )
                    td({key: "res"}, get_srv_reply_str(@props.result))
                    td({key: "command", title: @props.command_xml}, @props.command_xml.substring(0, 10))
                    td({key: "date"}, get_time(@props.date) + " (" + get_diff_time(@props.date) + ")")
                    td({key: "user"}, @props.user_name)
                    td(
                        {
                            key: "state"
                            className: "text-center  #{get_line_class(@props)}"
                        }
                        @props.state
                    )
                    td({key: "init"}, @props.initiator_name)
                    td({key: "nums", className: "text-center"}, @props.num_servers or "-")
                    td({key: "details", className: "text-center"}, details.join(", "))
                    td({key: "numo", className: "text-center"}, @props.num_objects or "-")
                    td({key: "cause"}, @props.cause)
                    td({key: "until"}, get_time(@props.valid_until))
                ]
            )
    )
]).directive("icswSystemBackgroundJobLine",
[
    "$templateCache", "icswSystemBackgroundJobFactory",
(
    $templateCache, icswSystemBackgroundJobFactory
) ->
    return {
        restrict: "EA"
        scope:
            line: "="
        link: (scope, el, attrs) ->
            ReactDOM.render(
                React.createElement(icswSystemBackgroundJobFactory, scope.line)
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
