angular.module(
    "icsw.tools.button",
    [
    ]
).service('icswToolsButtonConfigService', () ->
    get_config_for_button_type = (type) ->
        ret_obj = {}
        if type == "modify"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = "modify"
            ret_obj.icon_class = "fa fa-wrench"
        else if type == "create"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "create"
            ret_obj.icon_class = "fa fa-plus-circle"
        else if type == "delete"
            ret_obj.css_class = "btn-danger"
            ret_obj.button_value = "delete"
            ret_obj.icon_class = "fa fa-trash"
        else if type == "reload"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "reload"
            ret_obj.icon_class = "fa fa-refresh"
        else if type == "clear_selection"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "clear selection"
            ret_obj.icon_class = "fa fa-remove"
        else if type == "show"
            ret_obj.css_class = "btn-success"
            ret_obj.icon_class = ""
        else if type == "display"
            ret_obj.css_class = "btn-info"
            ret_obj.icon_class = "fa fa-search"
        else if type == "download"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "download"
            ret_obj.icon_class = "fa fa-download"
        else
            console.error "Invalid button type: ", type
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
).directive('icswToolsButton', ["icswToolsButtonConfigService", (icswToolsButtonsConfigService) ->
    return {
        restrict: "EA",
        template: """
    <button ng-attr-type="{{button_type}}" name="button" class="btn {{css_class}} {{additional_class}} {{icon_class}}"
            ng-disabled="is_disabled">
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
            disabled: '&'
        link: (scope, element, attrs) ->

            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload", "show", "clear_selection", "download"
            # - click: gets executed on click
            # - button-type: inserted into type, so use "button" or "submit" (default is "button")
            # - size: inserted into "btn-{{size}}", no default
            # - value: Custom text to display in button
            # - showValue: Custom text to show for show buttons if state is show
            # - hideValue: Custom text to show for show buttons if state is hide

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

            if attrs.disabled?
                scope.$watch(
                    () -> return scope.disabled()
                    (new_val) ->
                        scope.is_disabled = new_val
                )

            if attrs.type == "show"
                scope.$watch(scope.isShow
                    (new_val) ->
                        if new_val
                            scope.button_value = attrs.showValue or "show"
                        else
                            scope.button_value = attrs.hideValue or "hide"
                )
    }
])
