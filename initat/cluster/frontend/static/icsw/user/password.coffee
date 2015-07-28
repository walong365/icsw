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
).controller("icswUserPasswordCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "icswSimpleAjaxCall", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, icswSimpleAjaxCall, ICSW_URLS) ->
        $scope.$on("icsw.enter_password", () ->
            child_scope = $scope.$new()
            child_scope.PASSWORD_CHARACTER_COUNT = 16
            child_scope.pwd = {
                "pwd1" : ""
                "pwd2" : ""
            }
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.SESSION_LOGIN_ADDONS
                }
            ).then((xml) ->
                child_scope.PASSWORD_CHARACTER_COUNT = parseInt($(xml).find("value[name='password_character_count']").text())
            )
            child_scope.dyn_check = (val) ->
                child_scope.check()
                _rc = []
                if val.length < 8
                    _rc.push("has-error")
                return _rc.join(" ")
            child_scope.check = () ->
                if child_scope.pwd.pwd1 == "" and child_scope.pwd.pwd1 == child_scope.pwd.pwd2
                    child_scope.pwd_error = "empty passwords"
                    child_scope.pwd_error_class = "alert alert-warning"
                    return false
                else if child_scope.pwd.pwd1.length >= child_scope.PASSWORD_CHARACTER_COUNT and child_scope.pwd.pwd1 == child_scope.pwd.pwd2
                    child_scope.pwd_error = "passwords match"
                    child_scope.pwd_error_class = "alert alert-success"
                    return true
                else
                    child_scope.pwd_error = "passwords do not match or too short"
                    child_scope.pwd_error_class = "alert alert-danger"
                    return false
            msg = $compile($templateCache.get("icsw.user.password.set"))(child_scope)
            BootstrapDialog.show
                message : msg
                draggable: true
                size: BootstrapDialog.SIZE_MEDIUM
                title: "Enter password"
                closable: true
                closeByBackdrop: false
                buttons: [
                    {
                         cssClass: "btn-primary"
                         label: "Check"
                         action: (dialog) ->
                             child_scope.check()
                    },
                    {
                         icon: "glyphicon glyphicon-ok"
                         cssClass: "btn-success"
                         label: "Save"
                         action: (dialog) ->
                             if child_scope.check()
                                 $scope.$emit("icsw.set_password", child_scope.pwd.pwd1)
                                 dialog.close()
                    },
                    {
                        icon: "glyphicon glyphicon-remove"
                        label: "Cancel"
                        cssClass: "btn-warning"
                        action: (dialog) ->
                            dialog.close()
                    },
                ]
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
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
