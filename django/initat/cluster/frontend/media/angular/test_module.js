{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

render_error = (e, cur_inst) ->
    if e.data.detail
        noty
            text : e.data.detail
            type : "error"
            timeout : false
    if e.data.identifier
        for msg in e.data.identifier
            noty
                text : msg
                type : "error"
                timeout : false
    if e.data._reset_list
        $(e.data._reset_list).each (idx, entry) ->
            cur_inst[entry[0]] = entry[1]
    
render_ok = (data) ->
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
            
network_type_module = angular.module("icsw.network_type", ["ngResource", "ngCookies"])

network_type_module.config(['$httpProvider', 
    ($httpProvider) ->
        $httpProvider.defaults.xsrfCookieName = 'csrftoken'
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'
])

network_type_module.factory("network_type_rest", ["$resource",
    ($resource) ->
        return $resource("{% url 'rest:network_type_list' %}/:pk", {}, {
            query : {method : "GET" , isArray : true , params : { format : "json" }},
            save  : {method : "POST", isArray : false, params : { format : "json" }},
            update : {method : "PUT", isArray : false, params : { format : "json" }}
            delete  : {method : "DELETE", isArray : false, params : { format : "json" }},
        })
    ])
    
network_type_module.factory("network_device_type_rest", ["$resource",
    ($resource) ->
        return $resource("{% url 'rest:network_device_type_list' %}/:pk", {}, {
            query : {method : "GET" , isArray : true , params : { format : "json" }},
            save  : {method : "POST", isArray : false, params : { format : "json" }},
            update : {method : "PUT", isArray : false, params : { format : "json" }}
            delete  : {method : "DELETE", isArray : false, params : { format : "json" }},
        })
    ])
    
network_type_module.controller("overview_network_type", ["$scope", "network_type_rest"
    ($scope, network_type_rest) ->
        $scope.types = []
        $scope.network_types = {
            "b" : "boot"
            "p" : "prod"
            "s" : "slave"
            "o" : "other"
            "l" : "local"
        }
        network_type_rest.query(
            (response) ->
                $scope.types = response
                $scope.new_type = {identifier : "l", description : ""}
        )
        $scope.change = (entry) ->
            network_type_rest.update(
                {pk : entry.idx}
                entry
                (data) ->
                    data = render_ok(data)
                (e) -> render_error(e, entry)
            )
        $scope.delete = (entry) ->
            network_type_rest.delete(
                {pk : entry.idx}
                entry
                () -> 
                    noty
                        text : "deleted instance"
                    remove_by_idx($scope.types, entry.idx)
                (e) -> render_error(e, entry)
            )
        $scope.add_network_type = () ->
            network_type_rest.save(
                {}
                $scope.new_type
                (data) ->
                    data = render_ok(data) 
                    $scope.types.push(data)
                (e) -> render_error(e)
            )
    ])

network_type_module.controller("overview_network_device_type", ["$scope", "network_device_type_rest"
    ($scope, network_device_type_rest) ->
        $scope.types = []
        network_device_type_rest.query(
            (response) ->
                $scope.types = response
                $scope.new_type = {identifier : "eth", description : "", "mac_bytes" : 6}
        )
        $scope.change = (entry) ->
            network_device_type_rest.update(
                {pk : entry.idx}
                entry
                (data) ->
                    data = render_ok(data)
                (e) -> render_error(e, entry)
            )
        $scope.delete = (entry) ->
            network_device_type_rest.delete(
                {pk : entry.idx}
                entry
                () -> 
                    noty
                        text : "deleted instance"
                    remove_by_idx($scope.types, entry.idx)
                (e) -> render_error(e, entry)
            )
        $scope.add_network_type = () ->
            network_device_type_rest.save(
                {}
                $scope.new_type
                (data) ->
                    data = render_ok(data) 
                    $scope.types.push(data)
                (e) -> render_error(e)
            )
    ])
 
{% comment %}
network_type_module.directive("xtable",
    () ->
        return {
            restrict : "E"
            require : "^ngModel"
            transclude : true
            scope : true
            controller : ($scope, $element) ->
                # scope.data is set here to {} but scope.xx is undefined, nearly there...
                console.log $scope.data, $scope.xx, $element
                #entries = $scope.entries = []
            template : 
               "<div><table><tr ng-repeat='entry in entries'></tr></table></div>"
            replace : true
        }
    )
     
network_type_module.directive("mytable", 
    () ->
        return {
            restrict : "E"
            #require : "^ngModel"
            transclude : true
            scope : {}
            controller : ($scope, $element) ->
                console.log $scope, $element
                entries = $scope.entries = []
            template : 
               "<div>**{{ng-model}}**<table><tr ng-repeat='entry in entries'></tr></table></div>"
            link : (scope, element, attrs) ->
                console.log scope, element, attrs
            replace : true
        }
    )
{% endcomment %}

{% endinlinecoffeescript %}

</script>
