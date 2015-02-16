angular.module(
    "icsw.login",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap"
    ]
).controller("icswLoginCtrl", ["$scope", "$window", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService", "blockUI",
    ($scope, $window, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService, blockUI) ->
        $scope.login_hints = $window.LOGIN_HINTS
        $scope.ICSW_URLS = ICSW_URLS
        $scope.INIT_PRODUCT_NAME = $window.INIT_PRODUCT_NAME
        $scope.INIT_PRODUCT_VERSION = $window.INIT_PRODUCT_VERSION
        $scope.INIT_PRODUCT_FAMILY = $window.INIT_PRODUCT_FAMILY
        $scope.DJANGO_VERSION = $window.DJANGO_VERSION
        $scope.CLUSTER_NAME = $window.CLUSTER_NAME
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
