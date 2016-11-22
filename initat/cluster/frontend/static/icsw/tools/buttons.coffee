# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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

# unified button for angular

angular.module(
    "icsw.tools.button",
    []
).service('icswToolsButtonConfigService',
[
    'gettextCatalog',
(
    gettextCatalog
) ->
    get_config_for_button_type = (type) ->
        ret_obj = {}
        if type == "modify"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = gettextCatalog.getString("modify")
            ret_obj.icon_class = "fa fa-wrench"
        else if type == "resolve"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = "resolve"
            ret_obj.icon_class = "fa fa-ellipsis-h"
        else if type == "change"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "change"
            ret_obj.icon_class = "fa fa-wrench"
        else if type == "filter"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = "filter"
            ret_obj.icon_class = "fa fa-filter"
        else if type == "create"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettextCatalog.getString("create")
            ret_obj.icon_class = "fa fa-plus-circle"
        else if type == "delete"
            ret_obj.css_class = "btn-danger"
            ret_obj.button_value = gettextCatalog.getString("delete")
            ret_obj.icon_class = "fa fa-trash"
        else if type == "clear"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettextCatalog.getString("clear")
            ret_obj.icon_class = "fa fa-times"
        else if type == "reload"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettextCatalog.getString("reload")
            ret_obj.icon_class = "fa fa-refresh"
        else if type == "copy"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "copy"
            ret_obj.icon_class = "fa fa-copy"
        else if type == "stop"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettextCatalog.getString("stop")
            ret_obj.icon_class = "fa fa-hand-stop-o"
        else if type == "select"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = "Select"
            ret_obj.icon_class = "fa fa-check-square-o"
        else if type == "clear_selection"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettextCatalog.getString("clear selection")
            ret_obj.icon_class = "fa fa-remove"
        else if type == "show"
            ret_obj.css_class = "btn-success"
            ret_obj.icon_class = ""
        else if type == "toggle"
            ret_obj.css_class = "btn-primary"
            ret_obj.icon_class = "fa fa-refresh"
        else if type == "enable"
            ret_obj.icon_class = "fa fa-check"
            ret_obj.button_value = "enable"
            ret_obj.css_class = "btn-ok"
        else if type == "lock"
            ret_obj.icon_class = "fa fa-lock"
            ret_obj.button_value = "lock"
            ret_obj.css_class = "btn-ok"
        else if type == "disable"
            ret_obj.css_class = "btn-danger"
            ret_obj.button_value = "disable"
            ret_obj.icon_class = "fa fa-ban"
        else if type == "underscore"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = ""
            ret_obj.icon_class = "fa fa-minus"
        else if type == "close"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "close"
            ret_obj.icon_class = "fa fa-close"
        else if type == "info"
            ret_obj.css_class = "btn-info"
            ret_obj.icon_class = "fa fa-search"
        else if type == "display"
            ret_obj.css_class = "btn-info"
            ret_obj.icon_class = "fa fa-search"
        else if type == "search"
            ret_obj.css_class = "btn-primary"
            ret_obj.icon_class = "fa fa-search"
        else if type == "draw"
            ret_obj.css_class = "btn-primary"
            ret_obj.icon_class = "fa fa-pencil"
        else if type == "download"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettextCatalog.getString("download")
            ret_obj.icon_class = "fa fa-download"
        else if type == "upload"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettextCatalog.getString("upload")
            ret_obj.icon_class = "fa fa-upload"
        else if type == "revert"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "revert"
            ret_obj.icon_class = "fa fa-undo"
        else if type == "submit"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = gettextCatalog.getString("submit")
            ret_obj.icon_class = "fa fa-arrow-circle-right"
        else if type == "save"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "save"
            ret_obj.icon_class = "fa fa-save"
        else if type == "goto"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "go"
            ret_obj.icon_class = "fa fa-angle-double-right"
        else if type == "select_devices"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = "select devices"
            ret_obj.icon_class = "fa fa-desktop"
        else if type == "select_parent"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "select devices"
            ret_obj.icon_class = "fa fa-arrow-up"
        else if type == "bump"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "bump"
            ret_obj.icon_class = "glyphicon glyphicon-arrow-up"
        else if type == "image"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "build image"
            ret_obj.icon_class = "glyphicon glyphicon-hdd"
        else if type == "backward"
            ret_obj.css_class = "btn-default"
            ret_obj.button_value = ""
            ret_obj.icon_class = "glyphicon glyphicon-triangle-left"
        else if type == "forward"
            ret_obj.css_class = "btn-default"
            ret_obj.button_value = ""
            ret_obj.icon_class = "glyphicon glyphicon-triangle-right"
        else
            console.error "Invalid button type: #{type}"
        return ret_obj
    return {
        get_config_for_button_type:
            get_config_for_button_type
        get_css_class: (type) ->
            return get_config_for_button_type(type).css_class
        get_icon_class: (type) ->
            return get_config_for_button_type(type).icon_class
        get_css_and_icon_class: (type) ->
            conf = get_config_for_button_type(type)
            return conf.css_class + " " + conf.icon_class
    }
]).directive("icswToolsYesNo", [() ->
    return {
        restict: "EA"
        template: """
<button class="btn btn-xs form-control" ng-class="get_class()" style="width:100px;" ng-click="change_value($event)"> {{ get_value() }} </button>
"""
        scope:
            flag: "="
            callback: "=icswCallback"
        link: (scope, element, attrs) ->
            _yes_value = if attrs.icswYes? then attrs.icswYes else "yes"
            _no_value = if attrs.icswNo? then attrs.icswNo else "no"
            if attrs.disabled?
                _disabled = true
            else
                _disabled = false

            scope.change_value = ($event) ->
                if not _disabled
                    scope.flag = !scope.flag
                if attrs.icswCallback?
                    scope.callback($event)
                $event.preventDefault()

            scope.get_value = () ->
                return if scope.flag then _yes_value else _no_value

            scope.get_class = () ->
                return if scope.flag then "btn-success" else "btn-default"
    }
]).directive("icswToolsYesNoSmall", [() ->
    return {
        restict: "EA"
        template: """
<button class="btn btn-xs btn-default" ng-class="get_class()" style="width:50px;" ng-click="change_value($event)">{{ get_value() }}</button>
"""
        scope:
            flag: "="
        link: (scope, element, attrs) ->
            _yes_value = if attrs.icswYes? then attrs.icswYes else "yes"
            _no_value = if attrs.icswNo? then attrs.icswNo else "no"
            scope.change_value = ($event) ->
                if not attrs.ngClick?
                    # ngClick not defined in attributes
                    scope.flag = !scope.flag
                $event.preventDefault()

            scope.get_value = () ->
                return if scope.flag then _yes_value else _no_value

            scope.get_class = () ->
                return if scope.flag then "btn-success" else "btn-default"
    }
]).directive("icswToolsTriButton",
[
    "$q", "$templateCache", "$timeout",
(
    $q, $templateCache, $timeout,
) ->
    # tri-state button, ignore, set, unset (for selections)
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.tools.tri.button")
        scope:
            state: "=icswState"
            callback: "=icswCallback"
        link: (scope, element, attrs) ->
            if attrs.size
                _size = "btn-#{attrs.size}"
            else
                _size = ""

            new_state = () ->
                new_val = scope.state
                # state, 1: set, 0: ignore, -1:
                if new_val == 1
                    scope.css_class = "btn btn-success #{_size}"
                    scope.button_value = "set"
                else if new_val == 0
                    scope.css_class = "btn btn-warning #{_size}"
                    scope.button_value = "ignore"
                else if new_val == -1
                    scope.css_class = "btn btn-danger #{_size}"
                    scope.button_value = "not set"
                if scope.callback?
                    $timeout(
                        () ->
                            scope.callback(new_val)
                        0
                    )

            _cur_val = 666

            scope.toggle_state = ($event) ->
                scope.state++
                if scope.state == 2
                    scope.state = -1
                _cur_val = scope.state
                new_state()

            scope.$watch(
                "state",
                (new_val) ->
                    if new_val != _cur_val
                        _cur_val = new_val
                        new_state()
            )

    }
]).directive('icswToolsButton',
[
    "icswToolsButtonConfigService", "gettextCatalog", "$templateCache",
(
    icswToolsButtonsConfigService, gettextCatalog, $templateCache,
) ->
    return {
        restrict: "EA",
        template: $templateCache.get("icsw.tools.button")
        scope:
            isShow: '&'
            disabled: '&'
            isEnable: '&'
            isLock: '&'
            icsw_value: "=icswValue"
            hide_text: "&icswHideText"
        link: (scope, element, attrs) ->

            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload", "show", "clear_selection", "download"
            # - button-type: inserted into type, so use "button" or "submit" (default is "button")
            # - size: inserted into "btn-{{size}}", no default
            # - value: Custom text to display in button
            # - showValue: Custom text to show for show buttons if state is show
            # - hideValue: Custom text to show for show buttons if state is hide
            # - disabled: whether button is enabled

            b_type = attrs.type
            angular.extend(scope, icswToolsButtonsConfigService.get_config_for_button_type(b_type))

            # sane starting value
            scope.is_disabled = false

            if attrs.icswHideText?
                scope.show_text = false
                scope.button_value = ""
            else
                scope.show_text = true

            if attrs.icswValue?
                scope.$watch(
                    "icsw_value"
                    (new_val) ->
                        if scope.show_text
                            scope.button_value = new_val
                )

            else if attrs.value?
                scope.button_value = attrs.value

            if attrs.buttonType?
                scope.button_type = attrs.buttonType
            else
                scope.button_type = "button"

            if attrs.size?
                scope.additional_class = "btn-" + attrs.size
            else
                scope.additional_class = ""

            if attrs.disabled?
                scope.$watch(
                    () ->
                        return scope.disabled()
                    (new_val) ->
                        scope.is_disabled = new_val
                )
            if attrs.type == "show"
                scope.$watch(
                    scope.isShow
                    (new_val) ->
                        if new_val
                            scope.button_value = attrs.showValue or gettextCatalog.getString("hide")
                        else
                            scope.button_value = attrs.hideValue or gettextCatalog.getString("show")
                )
            else if attrs.type == "enable"
                scope.$watch(
                    scope.isEnable
                    (new_val) ->
                        if new_val
                            scope.button_value = gettextCatalog.getString("disable")
                            scope.css_class = "btn-warning"
                        else
                            scope.button_value = gettextCatalog.getString("enable")
                            scope.css_class = "btn-success"
                        if scope.icsw_value?
                            scope.button_value = scope.icsw_value
                )
            else if attrs.type == "lock"
                scope.$watch(
                    scope.isLock
                    (new_val) ->
                        if new_val
                            if scope.show_text
                                scope.button_value = gettextCatalog.getString("unlock")
                            scope.css_class = "btn-warning"
                            scope.icon_class = "fa fa-unlock"
                        else
                            if scope.show_text
                                scope.button_value = gettextCatalog.getString("lock")
                            scope.css_class = "btn-success"
                            scope.icon_class = "fa fa-lock"
                )
    }
]).directive('icswToolsButtonStatic',
[
    "icswToolsButtonConfigService", "gettextCatalog",
(
    icswToolsButtonsConfigService, gettextCatalog,
) ->
    # static button, doesnt change its face during his lifetime
    return {
        restrict: "EA",
        template: '<button type="button" class="btn btn-default" ng-disabled="is_disabled">value</button>'
        link: (scope, element, attrs) ->
            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload", "show", "clear_selection", "download"
            # - size: inserted into "btn-{{size}}", no default
            # - value: Custom text to display in button

            settings = icswToolsButtonsConfigService.get_config_for_button_type(attrs.type)

            if attrs.value?
                value = attrs.value
            else
                value = settings.button_value
            element.text(value)
            element.addClass("btn " + settings.css_class + " " + settings.icon_class)
            if attrs.size?
                element.addClass("btn-#{attrs.size}")

    }
])
