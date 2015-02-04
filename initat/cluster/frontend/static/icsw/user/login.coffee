login_module = angular.module("icsw.login", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap"])

login_module.controller("login_ctrl", ["$scope", "$window",
    ($scope, $window) ->
        $scope.login_hints = $window.LOGIN_HINTS
        $scope.medium_screen = () ->
            return $window.LOGIN_SCREEN_TYPE == "medium"
        $scope.big_screen = () ->
            return $window.LOGIN_SCREEN_TYPE == "big"
])
