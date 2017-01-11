# Copyright (C) 2012-2017 init.at
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
        $q.all(_wait_list).then(
            (data) ->
                _bi_info = data[0]
                _defer.resolve(_bi_info)
        )
        return _defer
    return {
        load: (client) ->
            return load_data(client).promise
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
        scope: true
        controller: "icswSystemBackgroundJobInfoCtrl"
    }
]).controller("icswSystemBackgroundJobInfoCtrl",
[
    "$q", "$scope", "icswSystemBackgroundInfoRestService",
(
    $q, $scope, icswSystemBackgroundInfoRestService,
) ->
    $scope.show_column = {}
    $scope.struct = {
        # data loaded
        data_loaded: false
        # list
        jobs: []
    }

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

    get_srv_reply_span_state = (srv_reply) ->
        return {
            0: "label-success"
            1: "label-warning"
            2: "label-danger"
            3: "label-danger"
            4: "label-primary"
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

    _salt_job = (entry) ->
        entry.$$srv_reply_str = get_srv_reply_str(entry.result)
        entry.$$command = entry.command_xml.substring(0, 10)
        entry.$$date = get_time(entry.date) + " (" + get_diff_time(entry.date) + ")"
        entry.$$state_class = get_line_class(entry)
        entry.$$valid_until = get_time(entry.valid_until)
        detail_spans = []
        for sub in entry.background_job_run_set
            detail_spans.push(
                {
                    "$$span_class": "label " + get_srv_reply_span_state(sub.state)
                    "$$title": sub.result
                    state: get_srv_reply_str(sub.state)
                }
            )
        entry.$$details = detail_spans

    _load = () ->
        $scope.struct.data_loaded = false
        $q.all(
            [
                icswSystemBackgroundInfoRestService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.jobs.length = 0
                for entry in data[0].plain()
                    _salt_job(entry)
                    $scope.struct.jobs.push(entry)
                $scope.struct.data_loaded = true
        )

    _load()

]).directive("icswSystemBackgroundJobLine",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.system.background.job.info.line")
    }
])
