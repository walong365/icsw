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

menu_module = angular.module(
    "icsw.layout.menu",
    [
        "ngSanitize", "ui.bootstrap",
    ]
).controller("menu_base", ["$scope", "$timeout", "$window", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService",
    ($scope, $timeout, $window, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
        $scope.is_authenticated = $window.IS_AUTHENTICATED
        $scope.CLUSTER_LICENSE = $window.CLUSTER_LICENSE
        $scope.GLOBAL_PERMISSIONS = $window.GLOBAL_PERMISSIONS
        $scope.OBJECT_PERMISSIONS = $window.OBJECT_PERMISSIONS
        $scope.NUM_BACKGROUND_JOBS = $window.NUM_BACKGROUND_JOBS
        $scope.SERVICE_TYPES = $window.SERVICE_TYPES
        $scope.HANDBOOK_PDF_PRESENT = $window.HANDBOOK_PDF_PRESENT
        $scope.ICSW_URLS = ICSW_URLS
        $scope.CURRENT_USER = $window.CURRENT_USER
        if $window.DOC_PAGE
            $scope.HANDBOOK_CHUNKS_PRESENT = $window.HANDBOOK_CHUNKS_PRESENT
            $scope.HANDBOOK_PAGE = $window.DOC_PAGE
        else
            $scope.HANDBOOK_CHUNKS_PRESENT = 0
            $scope.HANDBOOK_PAGE = "---"
        $scope.check_perm = (p_name) ->
            if p_name.split(".").length == 2
                p_name = "backbone.#{p_name}"
            if p_name of GLOBAL_PERMISSIONS
                return true
            else if p_name of OBJECT_PERMISSIONS
                return true
            else
                return false
        $scope.progress_iters = 0
        $scope.cur_gauges = {}
        $scope.num_gauges = 0
        $scope.get_progress_style = (obj) ->
            return {"width" : "#{obj.value}%"}
        $scope.show_time = () ->
            $scope.cur_time = moment().format("ddd, Do MMMM YYYY HH:mm:ss")
            $timeout($scope.show_time, 1000)
        $scope.update_progress_bar = () ->
            icswCallAjaxService
                url     : ICSW_URLS.BASE_GET_GAUGE_INFO
                hidden  : true
                success : (xml) =>
                    cur_pb = []
                    if icswParseXMLResponseService(xml)
                        $(xml).find("gauge_info gauge_element").each (idx, cur_g) ->
                            cur_g = $(cur_g)
                            idx = cur_g.attr("idx")
                            if idx of $scope.cur_gauges
                                $scope.cur_gauges[idx].info = cur_g.text()
                                $scope.cur_gauges[idx].value = parseInt(cur_g.attr("value"))
                            else
                                $scope.cur_gauges[idx] = {info : cur_g.text(), value : parseInt(cur_g.attr("value"))}
                            cur_pb.push(idx)
                    del_pbs = (cur_idx for cur_idx of $scope.cur_gauges when cur_idx not in cur_pb)
                    for del_pb in del_pbs
                        delete $scope.cur_gauges[del_pb]
                    #for cur_idx, value of $scope.cur_gauges
                    $scope.$apply(
                        $scope.num_gauges = cur_pb.length
                        if cur_pb.length or $scope.progress_iters
                            if $scope.progress_iters
                                $scope.progress_iters--
                            $timeout($scope.update_progress_bar, 1000)
                    )
        $scope.redirect_to_init = () ->
            window.location = "http://www.init.at"
            return false
        $scope.redirect_to_info = () ->
            window.location = ICSW_URLS.INFO_PAGE
            return false
        $scope.redirect_to_handbook = () ->
            window.location = "/cluster/doc/main.pdf"
            return false
        $scope.show_handbook_page = () ->
            window.open(
                ICSW_URLS.DYNDOC_PAGE_X.slice(0, -1) + $scope.HANDBOOK_PAGE
                "cluster documenation"
                "height=400,width=400,menubar=no,status=no,location=no,titlebar=no,resizeable=yes,scrollbars=yes"
            )
            return false
        $scope.redirect_to_bgj_info = () ->
            if $scope.check_perm('background_job.show_background')
                window.location = ICSW_URLS.USER_BACKGROUND_JOB_INFO
            return false
        $scope.get_background_job_class = () ->
            if $scope.NUM_BACKGROUND_JOBS < 4
                return "btn btn-xs btn-warning"
            else
                return "btn btn-xs btn-danger"
        $scope.rebuild_config = (cache_mode) ->
            # console.log ICSW_URLS.MON_CREATE_CONFIG, "+++"
            icswCallAjaxService
                url     : ICSW_URLS.MON_CREATE_CONFIG
                data    : {
                    "cache_mode" : cache_mode
                }
                title   : "create config"
                success : (xml) =>
                    if icswParseXMLResponseService(xml)
                        # make at least five iterations to catch slow startup of md-config-server
                        $scope.progress_iters = 5
                        $scope.update_progress_bar()
        $scope.show_time()
        $scope.$watch("navbar_size", (new_val) ->
            if new_val
                if $scope.is_authenticated
                    $("body").css("padding-top", parseInt(new_val["height"]) + 1)
        )
]).directive("icswLayoutMenubar", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar")
    }
]).factory("icswLayoutMenuAddon", () ->
    addons = []
    return addons
).directive("icswLayoutMenubarAddons", ["$templateCache", "$compile", "$window", "icswLayoutMenuAddon", ($templateCache, $compile, $window, icswLayoutMenuAddon) ->
    return {
        restrict: "EA"
        compile: (tElement, tAttr) ->
            return (scope, el, attrs) ->

                new_elems = []

                for addon in icswLayoutMenuAddon
                    _template_str = "<#{addon}></#{addon}>"
                    _new_el = $compile(_template_str)(scope).children()
                    new_elems.push(_new_el)

                el.replaceWith(new_elems)
    }
])
