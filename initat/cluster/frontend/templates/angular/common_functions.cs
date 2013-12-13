{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

build_lut = (list) ->
    lut = {}
    for value in list
        lut[value.idx] = value
    return lut

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
        @conf.act_page = parseInt(num)
        # indices start at zero
        pp = @conf.per_page
        @conf.start_idx = (@conf.act_page - 1 ) * pp
        @conf.end_idx = (@conf.act_page - 1) * pp + pp - 1
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
            if @conf.act_page > @conf.page_list.length
                @activate_page(@conf.page_list.length)
            else
                @activate_page(@conf.act_page)

class shared_data_source
    constructor: () ->
        @data = {}

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
        if url of @data
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
                    if typeof(resp.data) == "string"
                        if resp.data
                            resp.data = {"error" : resp.data}
                        else
                            resp.data = {}
                    for key, value of resp.data
                        if (typeof(value) == "object" or typeof(value) == "string") and not key.match(/^_/)
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
        cur_mod.service("sharedDataSource", [() ->
            return new shared_data_source()
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
                  '</input><span ng-show="pagSettings.conf.num_pages > 1">, </span>showing entries {{ pagSettings.conf.start_idx + 1 }} to {{ pagSettings.conf.end_idx + 1 }}</span>{% endverbatim %}'
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
    module.controller(name, ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", 
        ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q) ->
            $scope.settings = settings
            $scope.fn = settings.fn
            $scope.pagSettings = paginatorSettings.get_paginator(name)
            $scope.entries = []
            $scope.shared_data = sharedDataSource.data
            if $scope.settings.rest_url
                $scope.rest = Restangular.all($scope.settings.rest_url.slice(1))
                wait_list = [restDataSource.add_sources([$scope.settings.rest_url])[0]]
            else
                wait_list = []
            $scope.rest_data = {}
            $scope.modal_active = false
            if $scope.settings.rest_map
                for value, idx in $scope.settings.rest_map
                    $scope.rest_data[value.short] = restDataSource.load(value.url)
                    wait_list.push($scope.rest_data[value.short])
            $q.all(wait_list).then((data) ->
                base_idx = if $scope.settings.rest_url then 0 else -1
                for value, idx in data
                    if idx == base_idx
                        $scope.set_entries(value)
                    else
                        $scope.rest_data[$scope.settings.rest_map[idx - (1 + base_idx)].short] = value
            )
            if $scope.settings.init_fn
                $scope.settings.init_fn($scope)
            $scope.load_data = (url, options) ->
                return Restangular.all(url.slice(1)).getList(options)
            $scope.reload = () ->
                restDataSource.reload($scope.settings.rest_url).then((data) ->
                    $scope.set_entries(data)
                )
            $scope.set_entries = (data) ->
                if $scope.settings.entries_filter
                    $scope.entries = $filter("filter")(data, $scope.settings.entries_filter)
                else
                    $scope.entries = data
            $scope.modify = () ->
                if not $scope.form.$invalid
                    if $scope.create_mode
                        $scope.rest.post($scope.new_obj).then((new_data) ->
                            $scope.entries.push(new_data)
                            if $scope.pagSettings.conf.init
                                $scope.pagSettings.set_num_entries($scope.entries.length)
                            if $scope.settings.new_object_created
                                $scope.settings.new_object_created($scope.new_obj, new_data)
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
            $scope.create = (event) ->
                if typeof($scope.settings.new_object) == "function"
                    $scope.new_obj = $scope.settings.new_object($scope)
                else
                    $scope.new_obj = $scope.settings.new_object
                $scope.create_or_edit(event, true, $scope.new_obj)
            $scope.edit = (event, obj) ->
                $scope.create_or_edit(event, false, obj)
            $scope.create_or_edit = (event, create_or_edit, obj) ->
                $scope.edit_obj = obj
                $scope.create_mode = create_or_edit
                $scope.edit_div = $compile($templateCache.get($scope.settings.edit_template))($scope) 
                $scope.edit_div.simplemodal
                    #opacity      : 50
                    position     : [event.pageY, event.pageX]
                    #autoResize   : true
                    #autoPosition : true
                    onShow: (dialog) => 
                        dialog.container.draggable()
                        $("#simplemodal-container").css("height", "auto")
                        $scope.modal_active = true
                    onClose: (dialog) =>
                        $.simplemodal.close()
                        $scope.modal_active = false
            $scope.get_action_string = () ->
                return if $scope.create_mode then "Create" else "Modify"
            $scope.delete = (obj) ->
                if confirm($scope.settings.delete_confirm_str(obj))
                    obj.remove().then((resp) ->
                        noty
                            text : "deleted instance"
                        remove_by_idx($scope.entries, obj.idx)
                        if $scope.pagSettings.conf.init
                            $scope.pagSettings.set_num_entries($scope.entries.length)
                        if $scope.settings.post_delete
                            $scope.settings.post_delete($scope, obj)
                    )
    ])

angular.module(
    "init.csw.filters", []
).filter(
    "resolve_n2m", () ->
        return (in_array, f_array, n2m_key, null_msg) ->
            if typeof(in_array) == "string"
                # handle strings for chaining
                in_array = (parseInt(value) for value in in_array.split(/,\s*/))
            res = (value for key, value of f_array when typeof(value) == "object" and value and value.idx in in_array)
            #ret_str = (f_array[key][n2m_key] for key in in_array).join(", ")
            if res.length
                return (value[n2m_key] for value in res).join(", ")
            else
                if null_msg
                    return null_msg
                else
                    return "N/A"

).filter(
    "follow_fk", () ->
        return (in_value, scope, fk_model, fk_key, null_msg) ->
            if in_value != null
                return scope[fk_model][in_value][fk_key]
            else
                return null_msg
).filter(
    "array_lookup", () ->
        return (in_value, f_array, fk_key, null_msg) ->
            if in_value != null
                if fk_key
                    return (entry[fk_key] for key, entry of f_array when typeof(entry) == "object" and entry and entry["idx"] == in_value)[0]
                else
                    return (entry for key, entry of f_array when typeof(entry) == "object" and entry and entry["idx"] == in_value)[0]
            else
                return if null_msg then null_msg else "N/A"
).filter(
    "ip_fixed_width", () ->
        return (in_str) ->
            if in_str
                ip_field = in_str.split(".")
            else
                ip_field = ["?", "?", "?", "?"]
            return ("QQ#{part}".substr(-3, 3) for part in ip_field).join(".").replace(/Q/g, "&nbsp;")
).filter(
    "yesno1", () ->
        return (in_value) ->
            return if in_value then "yes" else "---"
).filter("limit_text", () ->
    return (text, max_len) ->
        if text.length > max_len
            return text[0..max_len] + "..."
        else
            return text
).filter("show_user", () ->
    return (user) ->
        if user
            if user.first_name and user.last_name
                return "#{user.login} (#{user.first_name} #{user.last_name})"
            else if user.first_name
                return "#{user.login} (#{user.first_name})"
            else if user.last_name
                return "#{user.login} (#{user.last_name})"
            else
                return "#{user.login}"
        else
            # in case user is undefined
            return "???"
).filter("datetime1", () ->
    return (cur_dt) ->
        return moment(cur_dt).format("ddd, D. MMM YYYY, HH:mm:ss") + ", " + moment(cur_dt).fromNow()
)

root.angular_module_setup = angular_module_setup
root.handle_reset = handle_reset
root.angular_add_simple_list_controller = angular_add_simple_list_controller
root.build_lut = build_lut

{% endinlinecoffeescript %}

</script>


