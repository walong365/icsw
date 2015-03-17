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
    "icsw.tools.button",
    [
    ]
).service('icswToolsButtonConfigService', ['gettext', (gettext) ->
    get_config_for_button_type = (type) ->
        ret_obj = {}
        if type == "modify"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = gettext("modify")
            ret_obj.icon_class = "fa fa-wrench"
        else if type == "create"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettext("create")
            ret_obj.icon_class = "fa fa-plus-circle"
        else if type == "delete"
            ret_obj.css_class = "btn-danger"
            ret_obj.button_value = gettext("delete")
            ret_obj.icon_class = "fa fa-trash"
        else if type == "reload"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettext("reload")
            ret_obj.icon_class = "fa fa-refresh"
        else if type == "clear_selection"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettext("clear selection")
            ret_obj.icon_class = "fa fa-remove"
        else if type == "show"
            ret_obj.css_class = "btn-success"
            ret_obj.icon_class = ""
        else if type == "enable"
            ret_obj.icon_class = ""
        else if type == "display"
            ret_obj.css_class = "btn-info"
            ret_obj.icon_class = "fa fa-search"
        else if type == "download"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettext("download")
            ret_obj.icon_class = "fa fa-download"
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
]).directive('icswToolsButton', ["icswToolsButtonConfigService", "gettext", (icswToolsButtonsConfigService, gettext) ->
    return {
        restrict: "EA",
        template: """
    <button ng-attr-type="{{button_type}}" name="button" class="btn {{css_class}} {{additional_class}} {{icon_class}}">
        {{ button_value }}
    </button>
<!--
Disabled for now as it forces a line break (cf. monitoring basic setup)
visible-md visible-lg
    <button ng-attr-type="{{button_type}}" name="button" class="hidden-md hidden-lg btn {{css_class}} {{additional_class}} {{icon_class}}" title="{{ button_value }}">
    </button>
-->
    """
        scope:
            isShow: '&'
            isEnable: '&'
        link: (scope, element, attrs) ->

            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload", "show", "clear_selection", "download"
            # - click: gets executed on click
            # - value: Custom text to display in button
            # - button-type: inserted into type, so use "button" or "submit" (default is "button")
            # - size: inserted into "btn-{{size}}", no default

            b_type = attrs.type
            angular.extend(scope, icswToolsButtonsConfigService.get_config_for_button_type(b_type))

            if attrs.value?
                scope.button_value = attrs.value

            if attrs.buttonType?
                scope.button_type = attrs.buttonType
            else
                scope.button_type = "button"

            if attrs.size?
                scope.additional_class = "btn-" + attrs.size
            else
                scope.additional_class = ""

            if attrs.type == "show"
                scope.$watch(scope.isShow
                    (new_val) ->
                        if new_val
                            scope.button_value = gettext("show")
                        else
                            scope.button_value = gettext("hide")
                )
            else if attrs.type == "enable"
                scope.$watch(scope.isEnable
                    (new_val) ->
                        if new_val
                            scope.button_value = gettext("disable")
                            scope.css_class = "btn-warning"
                        else
                            scope.button_value = gettext("enable")
                            scope.css_class = "btn-success"
                )
    }
])
