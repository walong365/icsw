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
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap"
    ]
).controller("icswLoginCtrl", ["$scope", "$window", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService", "blockUI", "initProduct"
    ($scope, $window, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService, blockUI, initProduct) ->
        $scope.login_hints = $window.LOGIN_HINTS
        $scope.ICSW_URLS = ICSW_URLS
        $scope.initProduct = initProduct
        $scope.INIT_PRODUCT_FAMILY = $window.INIT_PRODUCT_FAMILY
        $scope.DJANGO_VERSION = $window.DJANGO_VERSION
        $scope.CLUSTER_NAME = $window.CLUSTER_NAME
        $scope.CLUSTER_ID = $window.CLUSTER_ID
        #$scope.CSRF_TOKEN = $window.CSRF_TOKEN
        style_dict = {
            "medium" : {
                "gfx_class" : "col-xs-4"
                "gfx_style" : ""
                "login_class" : "col-xs-6"
            }
            "big" : {
                "gfx_class" : "col-md-offset-4 col-md-4"
                "gfx_style" : "margin-top:60px;"
                "login_class" : "col-md-offset-4 col-md-4"
            }
        }
        $scope.init_login = () ->
            $scope.login_data = {
                "username": ""
                "password": ""
                "next_url": $window.NEXT_URL
            }
        $scope.do_login = () ->
            blockUI.start()
            icswCallAjaxService
                url: ICSW_URLS.SESSION_LOGIN
                data:
                    blob: angular.toJson($scope.login_data)
                success: (xml) ->
                    if icswParseXMLResponseService(xml)
                        if $(xml).find("value[name='redirect']").length
                            _val = $(xml).find("value[name='redirect']").text()
                            $window.location = _val
                    else
                        blockUI.stop()
                        $scope.$apply(
                            $scope.init_login()
                        )
        $scope.gfx_class = () ->
            return style_dict[$window.LOGIN_SCREEN_TYPE]["gfx_class"]
        $scope.gfx_style = () ->
            return style_dict[$window.LOGIN_SCREEN_TYPE]["gfx_style"]
        $scope.login_class = () ->
            return style_dict[$window.LOGIN_SCREEN_TYPE]["login_class"]
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
