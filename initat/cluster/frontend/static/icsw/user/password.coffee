# Copyright (C) 2012-2016 init.at
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
).service("icswUserGetPassword",
[
    "$q", "$templateCache", "icswComplexModalService", "ICSW_URLS", "icswSimpleAjaxCall", "$compile",
(
    $q, $templateCache, icswComplexModalService, ICSW_URLS, icswSimpleAjaxCall, $compile,
) ->
    return (scope, user) ->
        child_scope = scope.$new()

        child_scope.user = user
        child_scope.PASSWOR_CHARACTER_COUNT = 16
        child_scope.pwd = {
            pwd1: ""
            pwd2: ""
        }

        defer = $q.defer()
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.SESSION_LOGIN_ADDONS
            }
        ).then(
            (xml) ->
                child_scope.PASSWORD_CHARACTER_COUNT = parseInt($(xml).find("value[name='password_character_count']").text())
        )

        # helper functions

        child_scope.dyn_check = (val) ->
            child_scope.check()
            _rc = []
            if val.length < child_scope.PASSWORD_CHARACTER_COUNT
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

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.user.password.set"))(child_scope)
                title: "Enter password for user '#{user.login}'"
                ok_callback: (modal) ->
                    d = $q.defer()
                    if child_scope.check()
                        user.$$password_ok = true
                        user.$$password = child_scope.pwd.pwd1
                        d.resolve("ok")
                    else
                        d.reject("ont ok")
                    return d.promise
                cancel_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("ok")
                    return d.promise
            }
        ).then(
            (fin) ->
                child_scope.$destroy()
                console.log child_scope.pwd
                defer.resolve("done")
        )
        return defer.promise

]).directive("icswUserAccountDetail",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.account.detail.form")
    }
])
