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
password_module = angular.module(
    "icsw.user.password",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).controller("icswUserPasswordCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $modal) ->
        $scope.$on("icsw.enter_password", () ->
            $modal.open
                template : $templateCache.get("icsw.user.password.set")
                controller : ["$scope", "$modalInstance", "scope", "$window", ($scope, $modalInstance, scope, $window) ->
                    $scope.PASSWORD_CHARACTER_COUNT = $window.PASSWORD_CHARACTER_COUNT
                    $scope.pwd = {
                        "pwd1" : ""
                        "pwd2" : ""
                    }
                    $scope.dyn_check = (val) ->
                        $scope.check()
                        _rc = []
                        if val.length < 8
                            _rc.push("has-error")
                        return _rc.join(" ")
                    $scope.ok = () ->
                        $modalInstance.close(true)
                        scope.$emit("icsw.set_password", $scope.pwd.pwd1)
                    $scope.check = () ->
                        if $scope.pwd.pwd1 == "" and $scope.pwd.pwd1 == $scope.pwd.pwd2
                            $scope.pwd_error = "empty passwords"
                            $scope.pwd_error_class = "alert alert-warning"
                            return false
                        else if $scope.pwd.pwd1.length >= $scope.PASSWORD_CHARACTER_COUNT and $scope.pwd.pwd1 == $scope.pwd.pwd2
                            $scope.pwd_error = "passwords match"
                            $scope.pwd_error_class = "alert alert-success"
                            return true
                        else
                            $scope.pwd_error = "passwords do not match or too short"
                            $scope.pwd_error_class = "alert alert-danger"
                            return false
                    $scope.cancel = () ->
                        $modalInstance.dismiss("cancel")
                ]
                backdrop : "static"
                resolve:
                    scope: () ->
                        return $scope
        )
]).directive("accountDetail", ["$templateCache", ($templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("account.detail.form")
        link: (scope, element, attrs) ->
            scope._cur_user = null
            scope.$watch(attrs["user"], (new_val) ->
                if new_val
                    scope._cur_user = new_val
            )
            scope.update_account = () ->
                scope._cur_user.put().then(
                   (data) ->
                   (resp) ->
                )
    }
])
