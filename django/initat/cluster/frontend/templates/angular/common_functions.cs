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

class paginator_root
    constructor: () ->
        @dict = {}
    get_paginator: (name) =>
        if name not in @dict
            @dict[name] = new paginator_class(name)
        return @dict[name]

class paginator_class
    constructor: (@name) ->
        @conf = {
            per_page    : 10
            num_entries : 0
            num_pages   : 0
            start_idx   : 0
            end_idx     : 0
            act_page    : 0
            page_list   : []
            init        : false
        }
    activate_page: (num) =>
        @conf.actpage = parseInt(num)
        # indices start at zero
        pp = @conf.per_page
        @conf.start_idx = (@conf.actpage - 1 ) * pp
        @conf.end_idx = (@conf.actpage - 1) * pp + pp - 1
        if @conf.end_idx >= @conf.num_entries
            @conf.end_idx = @conf.num_entries - 1
    set_num_entries: (num) =>
        @conf.init = true
        @conf.num_entries = num
        pp = @conf.per_page
        @conf.num_pages = parseInt((@conf.num_entries + pp - 1) / pp)
        if @conf.num_pages > 0
            @conf.page_list = (idx for idx in [1..@conf.num_pages])
        else
            @conf.page_list = []
        if @conf.act_page == 0
            @activate_page(1)
        else
            @activate_page(@conf.act_page)

class rest_data_source
    constructor: (@$q, @Restangular) ->
        @data = {}
    do_query: (q_type) =>    
        d = @$q.defer()
        result = q_type.getList().then(
           (response) ->
               d.resolve(response)
        )
        return d.promise
    load: (url) =>
        if url in @data
            return @get(url)
        else
            return @reload(url)
    reload: (url) =>
        @data[url] = @do_query(@Restangular.all(url.slice(1)))
        return @get(url) 
    add_sources: (in_list) =>
        q_list = []
        r_list = []
        for rest_url in in_list
            if rest_url not in @data
                sliced = rest_url.slice(1)
                @data[rest_url] = @do_query(@Restangular.all(sliced))
                q_list.push(@data[rest_url])
            r_list.push(@data[rest_url])
        if q_list
            @$q.all(q_list)
        return r_list
    get: (url) =>
        return @data[url]
  
angular_module_setup = (module_list, url_list=[]) ->
    #console.log url_list
    $(module_list).each (idx, cur_mod) ->
        cur_mod.config(['$httpProvider', 
            ($httpProvider) ->
                $httpProvider.defaults.xsrfCookieName = 'csrftoken'
                $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'
        ])
        cur_mod.filter("paginator", () ->
            return (arr, scope) ->
                if scope.pagSettings.conf.init 
                    return arr.slice(scope.pagSettings.conf.start_idx, scope.pagSettings.conf.end_idx + 1)
                else
                    return arr
        )
        cur_mod.filter("limit_text", () ->
            return (text, max_len) ->
                if text.length > max_len
                    return text[0..max_len] + "..."
                else
                    return text
        )
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
        # in fact identical ?
        # cur_mod.service("paginatorSettings", (paginator_class))
        cur_mod.service("paginatorSettings", [() ->
            return new paginator_root()
        ])
        cur_mod.service("restDataSource", ["$q", "Restangular", ($q, Restangular) ->
            return new rest_data_source($q, Restangular)
        ])
        cur_mod.directive("paginator", ($templateCache) ->
            link = (scope, element, attrs) ->
                scope.pagSettings.conf.per_page = parseInt(attrs.perPage)
                scope.activate_page = (page_num) ->
                    scope.pagSettings.activate_page(page_num)
                scope.$watch("entries", (new_el) ->
                    scope.pagSettings.set_num_entries(new_el.length)
                )
            return {
                restrict : "EA"
                scope:
                    entries     : "="
                    pagSettings : "="
                template : '{% verbatim %}<span ng-show="pagSettings.conf.num_entries">' +
                  '<input ng-show="pagSettings.conf.num_pages > 1" type="button" ng-repeat="pag_num in pagSettings.conf.page_list track by $index" value="{{ pag_num }}" ng-click="activate_page(pag_num)">' +
                  '</input><span ng-show="pagSettings.conf.num_pages > 1">, </span>showing from {{ pagSettings.conf.start_idx + 1 }} to {{ pagSettings.conf.end_idx + 1 }}</span>{% endverbatim %}'
                link     : link
            }
        )
        
        
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
    module.controller(name, ["$scope", "$compile", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", 
        ($scope, $compile, $templateCache, Restangular, paginatorSettings, restDataSource, $q) ->
            $scope.settings = settings
            $scope.pagSettings = paginatorSettings.get_paginator(name)
            $scope.entries = []
            wait_list = [restDataSource.add_sources([$scope.settings.rest_url])[0]]
            $scope.new_obj = $scope.settings.new_object
            $scope.rest_map = []
            if $scope.settings.rest_map
                for key, value of $scope.settings.rest_map
                    $scope.rest_map[key] = restDataSource.reload(value)
                    wait_list.push($scope.rest_map[key])
            $q.all(wait_list).then((data) ->
                # data ordering ? still unclear beyond the first element
                $scope.entries = data[0]
            )
            $scope.reload = () ->
                restDataSource.reload($scope.settings.rest_url).then((data) ->
                    $scope.entries = data
                    console.log data
                )
            $scope.get_entries = () ->
                pp = $scope.pagSettings.conf
                r_list = (obj for obj in $scope.entries[pp.start_idx .. pp.end_idx])
                return r_list
            $scope.modify = () ->
                if not $scope.form.$invalid
                    if $scope.create_mode
                        $scope.rest.post($scope.new_obj).then((new_data) ->
                            $scope.entries.push(new_data)
                            if $scope.settings.new_object_created
                                $scope.settings.new_object_created($scope.new_obj)
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


