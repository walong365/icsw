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
            
test_module = angular.module("icsw.test_module", ["ngRoute", "ngResource", "ngCookies"])

test_module.config(['$httpProvider', 
    ($httpProvider) ->
        $httpProvider.defaults.xsrfCookieName = 'csrftoken'
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'
])

test_module.factory("network_type", ["$resource",
    ($resource) ->
        return $resource("{% url 'rest:network_type_list' %}/:pk", {}, {
            query : {method : "GET" , isArray : true , params : { format : "json" }},
            save  : {method : "POST", isArray : false, params : { format : "json" }},
            update : {method : "PUT", isArray : false, params : { format : "json" }}
            delete  : {method : "DELETE", isArray : false, params : { format : "json" }},
        })
    ])
    
test_module.controller("overview", ["$scope", "network_type"
    ($scope, network_type) ->
        $scope.data = []
        $scope.network_types = [
            {
                "value" : "b",
                "long"  : "boot"
            },
            {
                "value" : "p",
                "long"  : "prod",
            },
            {
                "value" : "s",
                "long"  : "slave",
            },
            {
                "value" : "o",
                "long"  : "other",
            },
            {
                "value" : "l",
                "long"  : "local",
            }
        ]
        network_type.query(
            (response) ->
                $scope.data.issues = response
        )
        $scope.change = (issue) ->
            network_type.update(
                {pk : issue.idx}
                issue
                (data) ->
                    data = render_ok(data)
                (e) -> render_error(e, issue)
            )
        $scope.delete = (issue) ->
            network_type.delete(
                {pk : issue.idx}
                issue
                () -> 
                    noty
                        text : "deleted instance"
                    remove_by_idx($scope.data.issues, issue.idx)
                (e) -> render_error(e, issue)
            )
        $scope.add_network_type = () ->
            new_nw = {
                "identifier"  : $scope.network_type.identifier,
                "description" : $scope.network_type.description,
            }
            network_type.save(
                {}
                new_nw
                (data) ->
                    data = render_ok(data) 
                    $scope.data.issues.push(data)
                (e) -> render_error(e)
            )
    ])
 
{% comment %}
test_module.directive("xtable",
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
     
test_module.directive("mytable", 
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

root.test_module = test_module

{% endinlinecoffeescript %}

</script>
