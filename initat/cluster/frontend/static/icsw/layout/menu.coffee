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
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection",
    ]
).controller("menu_base", ["$scope", "$timeout", "$window", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService", "access_level_service", "initProduct", "icswLayoutSelectionDialogService", "icswActiveSelectionService",
    ($scope, $timeout, $window, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService, access_level_service, initProduct, icswLayoutSelectionDialogService, icswActiveSelectionService) ->
        $scope.is_authenticated = $window.IS_AUTHENTICATED
        $scope.NUM_BACKGROUND_JOBS = $window.NUM_BACKGROUND_JOBS
        $scope.SERVICE_TYPES = $window.SERVICE_TYPES
        $scope.HANDBOOK_PDF_PRESENT = $window.HANDBOOK_PDF_PRESENT
        $scope.ICSW_URLS = ICSW_URLS
        $scope.initProduct = initProduct
        $scope.quicksel = false
        $scope.CURRENT_USER = $window.CURRENT_USER
        if $window.DOC_PAGE
            $scope.HANDBOOK_CHUNKS_PRESENT = $window.HANDBOOK_CHUNKS_PRESENT
            $scope.HANDBOOK_PAGE = $window.DOC_PAGE
        else
            $scope.HANDBOOK_CHUNKS_PRESENT = 0
            $scope.HANDBOOK_PAGE = "---"
        access_level_service.install($scope)
        $scope.progress_iters = 0
        $scope.cur_gauges = {}
        $scope.num_gauges = 0
        $scope.get_progress_style = (obj) ->
            return {"width" : "#{obj.value}%"}
        $scope.show_time = () ->
            # set locale
            moment.locale("en")
            $scope.cur_time = moment().format("ddd, Do MMMM YYYY HH:mm:ss")
            $scope.$digest()
            $timeout($scope.show_time, 1000, false)
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
            window.location = ICSW_URLS.MAIN_INFO_PAGE
            return false
        $scope.redirect_to_handbook = () ->
            window.location = "/cluster/doc/#{initProduct.name.toLowerCase()}_handbook.pdf"
            return false
        $scope.show_handbook_page = () ->
            window.open(
                ICSW_URLS.DYNDOC_DOC_PAGE.slice(0, -1) + $scope.HANDBOOK_PAGE
                "cluster documenation"
                "height=500,width=600,menubar=no,status=no,location=no,titlebar=no,resizeable=yes,scrollbars=yes"
            )
            return false
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
        $timeout($scope.show_time, 1, false)
        $scope.$watch("navbar_size", (new_val) ->
            if new_val
                if $scope.is_authenticated
                    $("body").css("padding-top", parseInt(new_val["height"]) + 1)
        )
        $scope.device_selection = () ->
            icswLayoutSelectionDialogService.show_dialog($scope)
        $scope.device_quicksel = (onoff) ->
            if onoff != $scope.quicksel
                $scope.quicksel = onoff
                if $scope.quicksel
                    icswLayoutSelectionDialogService.quick_dialog($scope)
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
]).directive("icswBackgroundJobInfo", ["$templateCache", "ICSW_URLS", "icswSimpleAjaxCall", "$timeout", ($templateCache, ICSW_URLS, icswSimpleAjaxCall, $timeout) ->
    return {
        restrict: "EA"
        template: '<button type="button" ng-click="redirect_to_bgj_info()" title="number of background jobs"></button>'
        replace: true
        link: (scope, el, attrs) ->
            scope.background_jobs = 0
            el.hide()
            scope.redirect_to_bgj_info = () ->
                if scope.has_menu_permission('background_job.show_background')
                    window.location = ICSW_URLS.USER_BACKGROUND_JOB_INFO
                return false
            el.removeClass()
            el.addClass("btn btn-xs btn-warning")
            get_background_job_class = () ->
                if scope.background_jobs < 4
                    return "btn btn-xs btn-warning"
                else
                    return "btn btn-xs btn-danger"
            reload = () ->
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.MAIN_GET_NUMBER_OF_BACKGROUND_JOBS
                        dataType: "json"
                    }
                ).then((data) ->
                    scope.background_jobs = data["background_jobs"]
                    if scope.background_jobs
                        el.show()
                        el.removeClass()
                        el.addClass(get_background_job_class())
                        el.text(scope.background_jobs)
                    else
                        el.hide()
                )
                # reload every 30 seconds
                $timeout(reload, 30000)
            reload()
    }
])
