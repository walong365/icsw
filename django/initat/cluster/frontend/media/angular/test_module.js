{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}


root = exports ? this

test_module = angular.module("icsw.test_module", ["ngRoute", "ngResource"])

test_module.factory("network_type", ["$resource",
    ($resource) ->
        return $resource("{% url 'rest:network_type_list' %}/", {}, {
            query: {method : "GET", isArray : true, params : { format : "json" }} 
        })
    ])
    
test_module.controller("myc", ["$scope", "network_type"
    ($scope, network_type) ->
        $scope.data = {}
        network_type.query(
            (response) ->
                $scope.data.issues = response
        ) 
    ])
 
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
     
{% comment %}
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
