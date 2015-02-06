

button_module = angular.module(
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
        else
            console.error "Invalid button type: ", attrs.type
        return ret_obj
    return {
        get_config_for_button_type: get_config_for_button_type
        get_css_class_for_button_type: (type) -> return get_config_for_button_type(type).css_class
    }
).directive('icswToolsButton', ["icswToolsButtonConfigService", (icswToolsButtonsConfigService) ->
    return {
        restrict: "EA",
        template: """
    <button ng-attr-type="{{button_type}}" name="button" class="btn {{css_class}} {{additional_class}} {{icon_class}}"">
        {{ value }} {{ button_value }}
    </button>
    """
        scope:
            isShow: '&'
        link: (scope, element, attrs) ->

            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload", "show", "clear_selection"
            # - click: gets executed on click
            # - value: Custom text to display in button
            # - button-type: inserted into type, so use "button" or "submit" (default is "button")
            # - size: inserted into "btn-{{size}}", no default
            angular.extend(scope, icswToolsButtonsConfigService.get_config_for_button_type(attrs.type))

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
                            scope.button_value = "show"
                        else
                            scope.button_value = "hide"
                )
    }
])
