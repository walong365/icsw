{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

array_to_dict = (array, key) ->
    res = {}
    for idx, value of array
        if idx.match(/\d+/)
            # ignore stuff like $promise
            res[value[key]] = value
    return res

angular_module_setup = (module_list) ->
    $(module_list).each (idx, cur_mod) ->
        cur_mod.config(['$httpProvider', 
            ($httpProvider) ->
                $httpProvider.defaults.xsrfCookieName = 'csrftoken'
                $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'
        ])
        cur_mod.config(["RestangularProvider", 
            (RestangularProvider) ->
                RestangularProvider.setRestangularFields({
                    "id" : "idx"
                })
                RestangularProvider.setResponseInterceptor((data, operation, what, url, response, deferred) ->
                    if data._change_list
                        $(data._change_list).each (idx, entry) ->
                            noty
                                text : entry[0] + " : " + entry[1]
                        delete data._change_list
                    if data._messages
                        $(data._messages).each (idx, entry) ->
                            noty
                                text : entry
                    return data
                )
                RestangularProvider.setErrorInterceptor((resp) ->
                    for key, value of resp.data
                        if not key.match(/^_/)
                            noty
                                text : key + " : " + if typeof(value) == "string" then value else value.join(", ")
                                type : "error"
                                timeout : false
                    return true
                )
        ])
        
handle_reset = (data, e_list, idx) ->
    # console.log "HR", data, e_list, idx
    if data._reset_list
        scope_obj = (entry for key, entry of e_list when key.match(/\d+/) and entry.idx == idx)[0]
        $(data._reset_list).each (idx, entry) ->
            scope_obj[entry[0]] = entry[1]
        delete data._reset_list
   
angular_add_simple_list_controller = (module, name, settings) ->
    $(settings.template_cache_list).each (idx, t_name) ->
        short_name = t_name.replace(/.html$/g, "").replace(/_/g, "")
        module.directive(short_name, ($templateCache) ->
            return {
                restrict : "EA"
                template : $templateCache.get(t_name)
            }
        )
    module.controller(name, ["$scope", "$compile", "$templateCache", "Restangular",
        ($scope, $compile, $templateCache, Restangular) ->
            $scope.settings = settings
            $scope.entries = []
            $scope.rest = Restangular.all($scope.settings.rest_url.slice(1))
            $scope.reload = () ->
                $scope.rest.getList().then((response) ->
                    $scope.entries = response
                )
            $scope.reload()
            $scope.modify = () ->
                if not $scope.form.$invalid
                    if $scope.create_mode
                        $scope.rest.post($scope.new_obj).then((new_data) ->
                            $scope.entries.push(new_data)
                            #$scope.new_obj.description = ""
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
                $scope.edit_div = $compile($templateCache.get($scope.settings.edit_template))($scope) 
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
                if confirm($scope.settings.delete_confirm_str(obj))
                    obj.remove().then((resp) ->
                        noty
                            text : "deleted instance"
                        remove_by_idx($scope.entries, obj.idx)
                    )
    ])

root.angular_module_setup = angular_module_setup
root.array_to_dict = array_to_dict
root.handle_reset = handle_reset
root.angular_add_simple_list_controller = angular_add_simple_list_controller

{% endinlinecoffeescript %}

</script>


