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
).controller("info_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "access_level_service", "$timeout", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, access_level_service, $timeout, ICSW_URLS) ->
        access_level_service.install($scope)
        $scope.pagSettings = paginatorSettings.get_paginator("jobs", $scope)
        $scope.jobs = []
        $scope.reload = () ->
            # force reload
            restDataSource.reset()
            wait_list = restDataSource.add_sources([
                [ICSW_URLS.REST_BACKGROUND_JOB_LIST, {}]
            ])
            $q.all(wait_list).then((data) ->
                $scope.jobs = data[0]
            )
        $timeout($scope.reload, 5000)
        $scope.get_diff_time = (dt) ->
            if dt
                return moment(dt).fromNow()
            else
                return "???"
        $scope.get_time = (dt) ->
            if dt
                return moment(dt).format(DT_FORM)
            else
                return "---"
        $scope._runtime = (diff) ->
            if diff
                # seconds
                return diff + "s"
            else
                return "< 1s"
        $scope.get_result_str = (job) ->
            return {
                0: "OK"
                1: "Warn"
                2: "Error"
                3: "Critical"
                4: "Unknown"
            }[job.result]
        $scope.get_line_class = (job) ->
            if job.result == 0
                return ""
            else if job.result == 1
                return "warning"
            else
                return "danger"
        $scope.reload()
])
