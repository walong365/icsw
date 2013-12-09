{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

package_module = angular.module("icsw.package", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([package_module])

angular_add_simple_list_controller(
    package_module,
    "package_repo_base",
    {
        rest_url            : "{% url 'rest:package_repo_list' %}"
        delete_confirm_str  : (obj) -> return "Really delete Package repository '#{obj.name}' ?"
        template_cache_list : ["package_repo_row.html", "package_repo_head.html"]
        fn :
            toggle : (obj) ->
                obj.publish_to_nodes = if obj.publish_to_nodes then false else true
                obj.put()
            rescan : ($scope) ->
                $.blockUI()
                $.ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "rescan_repos"
                    }
                    success : (xml) ->
                        $.unblockUI()
                        if parse_xml_response(xml)
                            $scope.reload()
            sync : () ->
                $.blockUI()
                $.ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "sync_repos"
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)
    }
)

angular_add_simple_list_controller(
    package_module,
    "package_search_base",
    {
        rest_url            : "{% url 'rest:package_search_list' %}"
        edit_template       : "package_search.html"
        rest_map            : [
            {"short" : "user"            , "url" : "{% url 'rest:user_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Package search '#{obj.name}' ?"
        template_cache_list : ["package_search_row.html", "package_search_head.html"]
        entries_filter      : {deleted : false}
        new_object          : {"search_string" : "", "user" : {{ request.user.pk }}}
        new_object_created  : (new_obj, srv_data) -> 
            new_obj.search_string = ""
            $.ajax
                url     : "{% url 'pack:repo_overview' %}"
                data    : {
                    "mode" : "reload_searches"
                }
                success : (xml) ->
                    parse_xml_response(xml)
        fn:
            retry : ($scope, obj) ->
                if $scope.shared_data.result_obj and $scope.shared_data.result_obj.idx == obj.idx
                    $scope.shared_data.result_obj = undefined
                $.ajax
                    url     : "{% url 'pack:retry_search' %}"
                    data    : {
                        "pk" : obj.idx
                    }
                    success : (xml) ->
                        parse_xml_response(xml)
                        $scope.reload()
            show : ($scope, obj) ->
                $scope.shared_data.result_obj = obj
        init_fn:
            ($scope) ->
                $(document).everyTime(5000, "show_time", (i) ->
                    if not $scope.modal_active
                        # only reload if no modal is currently active
                        $scope.reload()
                )
    }
)

angular_add_simple_list_controller(
    package_module,
    "package_search_result_base",
    {
        #rest_url            : "{% url 'rest:package_search_list' %}"
        edit_template       : "package_search.html"
        rest_map            : [
            {"short" : "package_repo", "url" : "{% url 'rest:package_repo_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Package search result '#{obj.name}-#{obj.version}' ?"
        template_cache_list : ["package_search_result_row.html", "package_search_result_head.html"]
        init_fn:
            ($scope) ->
                $scope.$watch(
                    "shared_data"
                    (new_el) ->
                        if $scope.shared_data.result_obj
                            $scope.load_data(
                                "{% url 'rest:package_search_result_list' %}",
                                {"package_search" : $scope.shared_data.result_obj.idx}
                            ).then(
                                (data) ->
                                    $scope.entries = data
                            )
                        else
                            $scope.entries = []
                    true
                )
        fn:
            take : (obj) ->
                obj.copied = 1
                $.ajax
                    url     : "{% url 'pack:use_package' %}"
                    data    : {
                        "pk" : obj.idx
                    }
                    success : (xml) ->
                        if not parse_xml_response(xml)
                            obj.copied = 0
    }
)

{% endinlinecoffeescript %}

</script>
