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
angular.module(
    "icsw.login",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "icsw.user.license",
    ]
).controller("icswLoginCtrl", ["$scope", "$window", "ICSW_URLS", "icswSimpleAjaxCall", "icswParseXMLResponseService", "blockUI", "initProduct", "icswUserLicenseDataService", "$q", "$state", "icswCSRFService", "icswUserService",
    ($scope, $window, ICSW_URLS, icswSimpleAjaxCall, icswParseXMLResponseService, blockUI, initProduct, icswUserLicenseDataService, $q, $state, icswCSRFService, icswUserService) ->
        $scope.ICSW_URLS = ICSW_URLS
        $scope.initProduct = initProduct
        $scope.lds = icswUserLicenseDataService
        $scope.django_version = "---"
        $scope.CLUSTER_NAME = ""
        $scope.CLUSTER_ID = ""
        $scope.LOGIN_SCREEN_TYPE = "big"
        $scope.DATABASE_VERSION = ""
        $scope.login_hints = []
        $scope.disabled = true
        style_dict = {
            "medium" : {
                "gfx_class" : "col-xs-4"
                "gfx_style" : {}
                "login_class" : "col-xs-6"
            }
            "big" : {
                "gfx_class" : "col-md-offset-4 col-md-4"
                "gfx_style" : {"margin-top": "60px"}
                "login_class" : "col-md-offset-4 col-md-4"
            }
        }
        first_call = true
        $scope.init_login = () ->
            $q.all(
                [
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.SESSION_LOGIN_ADDONS
                        }
                    ),
                    icswSimpleAjaxCall(
                        {
                            url: ICSW_URLS.MAIN_GET_CLUSTER_INFO,
                            dataType: "json"
                        }
                    ),
                ]
            ).then(
                (data) ->
                    xml = data[0]
                    $scope.login_hints = angular.fromJson($(xml).find("value[name='login_hints']").text())
                    $scope.django_version = $(xml).find("value[name='django_version']").text()
                    $scope.LOGIN_SCREEN_TYPE = $(xml).find("value[name='login_screen_type']").text()
                    $scope.disabled = false
                    $scope.CLUSTER_NAME = data[1].CLUSTER_NAME
                    $scope.CLUSTER_ID = data[1].CLUSTER_ID
                    $scope.DATABASE_VERSION = data[1].DATABASE_VERSION
                    $scope.SOFTWARE_VERSION = data[1].SOFTWARE_VERSION
                    $scope.MODELS_VERSION = data[1].MODELS_VERSION
                    if first_call
                        first_call = false
                        $scope.login_data.next_url = $(xml).find("value[name='next_url']").text()
            )
            $scope.login_data = {
                "username": ""
                "password": ""
                "next_url": ""
            }

        $scope.do_login = () ->
            blockUI.start("Logging in...")
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.SESSION_LOGIN
                    data:
                        blob: angular.toJson($scope.login_data)
                }
            ).then(
                (xml) ->
                    # blockUI.stop()
                    if $(xml).find("value[name='redirect']").length
                        _val = $(xml).find("value[name='redirect']").text()
                        # clear token
                        icswCSRFService.clear_token()
                        icswCSRFService.get_token().then(
                            (csrf_token) ->
                                icswUserService.load().then(
                                    (_user) ->
                                        blockUI.stop()
                                        $state.go(_val)
                                )
                        )
                (error) ->
                    blockUI.stop()
                    $scope.init_login()
            )
        $scope.gfx_class = () ->
            return style_dict[$scope.LOGIN_SCREEN_TYPE]["gfx_class"]
        $scope.gfx_style = () ->
            return style_dict[$scope.LOGIN_SCREEN_TYPE]["gfx_style"]
        $scope.login_class = () ->
            return style_dict[$scope.LOGIN_SCREEN_TYPE]["login_class"]
        $scope.init_login()
]).directive("icswLoginForm", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("authentication.form")
    }
]).directive("icswLoginPage", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.user.login.page")
    }
])
