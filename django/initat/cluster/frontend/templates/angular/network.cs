{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

angular.module(
    "ip_filters", []
).filter(
    "resolve_n2m", () ->
        return (in_array, scope, n2m_field, n2m_key) ->
            ret_str = (scope[n2m_field][key][n2m_key] for key in in_array).join(", ")
            if ret_str
                return ret_str
            else
                return "no " + n2m_field.replace(/_/g, " ") + " defined"
).filter(
    "follow_fk", () ->
        return (in_value, scope, fk_model, fk_key, null_msg) ->
            if in_value != null
                return scope[fk_model][in_value][fk_key]
            else
                return null_msg
).filter(
    "array_lookup", () ->
        return (in_value, scope, fk_model, fk_key, null_msg) ->
            if in_value != null
                return (entry[fk_key] for key, entry of scope[fk_model] when typeof(entry) == "object" and entry and entry["idx"] == in_value)[0]
            else
                return null_msg
)

network_module = angular.module("icsw.network", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "ip_filters", "localytics.directives", "restangular"])

angular_module_setup([network_module])

network_module.constant("network_types", {
    "b" : "boot"
    "p" : "prod"
    "s" : "slave"
    "o" : "other"
    "l" : "local"
})

network_module.controller("network_type", ["$scope", "$compile", "$templateCache", "network_types", "Restangular",
    ($scope, $compile, $templateCache, network_types, Restangular) ->
        $scope.entries = []
        $scope.network_types = network_types
        $scope.rest = Restangular.all("{% url 'rest:network_type_list' %}".slice(1))
        $scope.rest.getList().then((response) ->
            $scope.entries = response
            $scope.new_obj = {identifier : "p", description : ""}
        )
        $scope.modify = () ->
            if not $scope.form.$invalid
                if $scope.create_mode
                    $scope.rest.post($scope.new_obj).then((new_data) ->
                        $scope.entries.push(new_data)
                        $scope.new_obj.description = ""
                    )
                else
                    $scope.edit_obj.put().then(
                        (data) -> 
                            $.simplemodal.close()
                            handle_reset(data, $scope.entries, $scope.edit_obj.idx)
                        (resp) -> handle_reset(resp.data, $scope.entries, $scope.edit_obj.idx)
                    )
        $scope.form_error = (field_name) ->
            if $scope.form[field_name].$valid
                return ""
            else
                return "has-error"
        $scope.create = ($event) ->
            $scope.create_or_edit(event, true, $scope.new_obj)
        $scope.edit = ($event, obj) ->
            $scope.create_or_edit(event, false, obj)
        $scope.create_or_edit = ($event, create_or_edit, obj) ->
            $scope.edit_obj = obj
            $scope.create_mode = create_or_edit
            $scope.edit_div = $compile($templateCache.get("network_type.html"))($scope) 
            $scope.edit_div.simplemodal
                #opacity      : 50
                position     : [$event.pageY, $event.pageX]
                #autoResize   : true
                #autoPosition : true
                onShow: (dialog) => 
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                onClose: (dialog) =>
                    $.simplemodal.close()
        $scope.get_action_string = () ->
            return if $scope.create_mode then "Create" else "Modify"
        $scope.delete = (obj) ->
            if confirm("really delete network type '#{obj.description}' ?")
                obj.remove().then((resp) ->
                    noty
                        text : "deleted instance"
                    remove_by_idx($scope.entries, obj.idx)
                )
    ])
    
network_module.directive("networkrow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("network_row.html")
    }
)

network_module.directive("networkhead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("network_head.html")
    }
)

network_module.directive("networktyperow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("network_type_row.html")
    }
)

network_module.directive("networktypehead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("network_type_head.html")
    }
)

network_module.directive("networkdevicetyperow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("network_device_type_row.html")
    }
)

network_module.directive("networkdevicetypehead", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("network_device_type_head.html")
    }
)

network_module.controller("network_device_type", ["$scope", "$compile", "$templateCache", "Restangular"
    ($scope, $compile, $templateCache, Restangular) ->
        $scope.entries = []
        $scope.rest = Restangular.all("{% url 'rest:network_device_type_list' %}".slice(1))
        $scope.rest.getList().then((response) ->
            $scope.entries = response
            $scope.new_obj = {identifier : "eth", description : "", "mac_bytes" : 6}
        )
        $scope.modify = () ->
            if not $scope.form.$invalid
                if $scope.create_mode
                    $scope.rest.post($scope.new_obj).then((new_data) ->
                        $scope.entries.push(new_data)
                        $scope.new_obj.identifier = ""
                    )
                else
                    $scope.edit_obj.put().then(
                        (data) -> 
                            $.simplemodal.close()
                            handle_reset(data, $scope.entries, $scope.edit_obj.idx)
                        (resp) -> handle_reset(resp.data, $scope.entries, $scope.edit_obj.idx)
                    )
        $scope.form_error = (field_name) ->
            if $scope.form[field_name].$valid
                return ""
            else
                return "has-error"
        $scope.create = ($event) ->
            $scope.create_or_edit(event, true, $scope.new_obj)
        $scope.edit = ($event, obj) ->
            $scope.create_or_edit(event, false, obj)
        $scope.create_or_edit = ($event, create_or_edit, obj) ->
            $scope.edit_obj = obj
            $scope.create_mode = create_or_edit
            $scope.edit_div = $compile($templateCache.get("network_device_type.html"))($scope) 
            $scope.edit_div.simplemodal
                #opacity      : 50
                position     : [$event.pageY, $event.pageX]
                #autoResize   : true
                #autoPosition : true
                onShow: (dialog) => 
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                onClose: (dialog) =>
                    $.simplemodal.close()
        $scope.get_action_string = () ->
            return if $scope.create_mode then "Create" else "Modify"
        $scope.delete = (obj) ->
            if confirm("really delete network device type '#{obj.description}' ?") 
                obj.remove().then((resp) ->
                    noty
                        text : "deleted instance"
                    remove_by_idx($scope.entries, obj.idx)
                )
    ])

network_module.controller("network", ["$scope", "$compile", "$templateCache", "$q", "Restangular",
    ($scope, $compile, $templateCache, $q, Restangular) ->
        #$scope.entries = []
        $scope.rest_network_types = Restangular.all("{% url 'rest:network_type_list' %}".slice(1))
        $scope.rest_network_device_types = Restangular.all("{% url 'rest:network_device_type_list' %}".slice(1))
        $scope.rest = Restangular.all("{% url 'rest:network_list' %}".slice(1))
        do_query = (q_type) ->
            d = $q.defer()
            result = q_type.getList().then(
               (response) ->
                   d.resolve(response)
            )
            return d.promise
        $q.all([
            do_query($scope.rest_network_types)
            do_query($scope.rest_network_device_types)
            do_query($scope.rest)
        ]).then((data) ->
            $scope.network_types = array_to_dict(data[0], "idx")
            $scope.network_device_types = array_to_dict(data[1], "idx")
            $scope.entries = data[2]
            $scope.new_obj = {identifier : "", network_type : (entry["idx"] for key, entry of $scope.network_types when entry["identifier"] == "o")[0]}
        )
        $scope.ip_fill_up = (in_str) ->
            if in_str
                ip_field = in_str.split(".")
            else
                ip_field = ["?", "?", "?", "?"]
            return ("QQ#{part}".substr(-3, 3) for part in ip_field).join(".").replace(/Q/g, "&nbsp;")
        $scope.modify = () ->
            if not $scope.form.$invalid
                if $scope.create_mode
                    $scope.rest.post($scope.new_obj).then((new_data) ->
                        $scope.entries.push(new_data)
                        $scope.new_obj.identifier = ""
                    )
                else
                    $scope.edit_obj.put().then(
                        (data) ->
                            $.simplemodal.close()
                            handle_reset(data, $scope.entries, $scope.edit_obj.idx)
                        (resp) -> handle_reset(resp.data, $scope.entries, $scope.edit_obj.idx)
                    )
        $scope.form_error = (field_name) ->
            if $scope.form[field_name].$valid
                return ""
            else
                return "has-error"
        $scope.create = ($event) ->
            $scope.create_or_edit(event, true, $scope.new_obj)
        $scope.edit = ($event, obj) ->
            $scope.create_or_edit(event, false, obj)
        $scope.create_or_edit = ($event, create_or_edit, obj) ->
            $scope.edit_obj = obj
            $scope.create_mode = create_or_edit
            $scope.edit_div = $compile($templateCache.get("network.html"))($scope) 
            $scope.edit_div.simplemodal
                #opacity      : 50
                position     : [$event.pageY, $event.pageX]
                #autoResize   : true
                #autoPosition : true
                onShow: (dialog) => 
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                onClose: (dialog) =>
                    $.simplemodal.close()
        $scope.get_action_string = () ->
            return if $scope.create_mode then "Create" else "Modify"
        $scope.delete = (obj) ->
            if confirm("really delete network '#{obj.description}' ?") 
                obj.remove().then((resp) ->
                    noty
                        text : "deleted instance"
                    remove_by_idx($scope.entries, obj.idx)
                )
        $scope.get_production_networks = () ->
            return (entry for key, entry of $scope.entries when key.match(/\d+/) and $scope.network_types[entry["network_type"]].identifier == "p")
        $scope.is_slave_network = (nw_type) ->
            return $scope.network_types[nw_type].identifier == "s"
])

{% endinlinecoffeescript %}

</script>
