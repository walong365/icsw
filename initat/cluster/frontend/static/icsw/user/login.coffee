angular.module(
    "icsw.login",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap"
    ]
).controller("icswLoginCtrl", ["$scope", "$window", "ICSW_URLS",
    ($scope, $window, ICSW_URLS) ->
        $scope.login_hints = $window.LOGIN_HINTS
        $scope.ICSW_URLS = ICSW_URLS
        $scope.INIT_PRODUCT_NAME = $window.INIT_PRODUCT_NAME
        $scope.INIT_PRODUCT_VERSION = $window.INIT_PRODUCT_VERSION
        $scope.INIT_PRODUCT_FAMILY = $window.INIT_PRODUCT_FAMILY
        $scope.DJANGO_VERSION = $window.DJANGO_VERSION
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
        $scope.gfx_class = () ->
            return style_dict[$window.LOGIN_SCREEN_TYPE]["gfx_class"]
        $scope.gfx_style = () ->
            return style_dict[$window.LOGIN_SCREEN_TYPE]["gfx_style"]
        $scope.login_class = () ->
            return style_dict[$window.LOGIN_SCREEN_TYPE]["login_class"]
]).directive("icswLoginForm", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("authentication.form.working")
    }
])
