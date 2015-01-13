{% load coffeescript %}

<script type="text/javascript">


{% inlinecoffeescript %}

{% verbatim %}

monitoring_overview_template = """

<div class="row">
    <div class="col-md-6">

                <span ng-class="" ng-click="myhidden = !myhidden" class="ng-binding label label-primary"> click {{ myhidden }} </span>

    <div st-table="rowCollection" >
             <custom-search></custom-search>

    <table class="table table-striped">
        <thead>
        <tr>
             <th st-sort="firstName">first name</th>
             <th ng-hide="myhidden" st-sort="lastName">last name</th>
             <th st-sort="birthDate">birth date</th>
             <th st-sort="balance" st-skip-natural="true" >balance</th>
             <th>email</th>
         </tr>
         <tr>
         <th>
             <input st-search="'firstName'" placeholder="search for firstname" class="input-sm form-control" type="search"/>
         here
         </th>
         <th>
         </th>
        </thead>

        <tbody>
            <tr ng-repeat="row in rowCollection">
                 <td>{{row.firstName | uppercase}}</td>
                 <td ng-hide="myhidden">{{row.lastName}}</td>
                 <td>{{row.birthDate | date}}</td>
                 <td>{{row.balance | currency}}</td>
                 <td><a ng-href="mailto:{{row.email}}">email</a>
                 
                 </td>
            </tr>
        </tbody>

        <tfoot>
            <tr>
                <td colspan="5" class="text-center">
                    <div st-pagination="" st-template="mytemplate.html" st-items-by-page="3" st-displayed-pages="3"></div>
                </td>
            </tr>
        </tfoot>
    </table>
    </div>

<table st-table="displayed_data" st-safe-src="actual_data" class="table table-bordered">
    <thead>
        <tr>
            <th>first name</th>
            <th st-sort="lastName">last name</th>
            <th st-sort="birthDate">birth date</th>
            <th st-sort="balance">balance</th>
            <th>email</th>
        </tr>
    </thead>
    <tbody>
    <tr ng-repeat="row in displayed_data" ng-if="!row.hidden"> 
            <td ng-if="row.special" colspan="6"> fancy extra line {{ row.content }}</td>

            <td ng-if="!row.special">{{row.firstName}}</td>
            <td ng-if="!row.special">{{row.lastName}}</td>

            <td ng-if="!row.special">{{row.birthDate}}</td>
            <td ng-if="!row.special">{{row.balance}}</td>
            <td ng-if="!row.special">{{row.email}}

                <span ng-class="" ng-click="fun(row)" class="ng-binding label label-primary"> add </span>
</td>
            <td ng-if="!row.special" class="text-center">
                <span ng-class="" ng-click="row.expanded = !row.expanded; toggled(row)" class="ng-binding label label-primary">
                <span ng_class="" class="glyphicon glyphicon-chevron-right">
                </span>
                {{ row.expanded }}
                </span>&nbsp;
            </td> 
    </tr>
    </tbody>
</table>

    </div>
</div>
"""

{% endverbatim %}

root = exports ? this

monitoring_overview_module = angular.module("icsw.monitoring_overview", 
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ui.bootstrap.datetimepicker", "smart-table"])

angular_module_setup([monitoring_overview_module])

monitoring_overview_module.controller("monitoring_overview_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout) ->
           $scope.rowCollection = [
                    {firstName: 'Laurent', lastName: 'Renard', birthDate: new Date('1987-05-21'), balance: 102, email: 'whatever@gmail.com',},
                    {firstName: 'Blandine', lastName: 'Faivre', birthDate: new Date('1987-04-25'), balance: -2323.22, email: 'oufblandou@gmail.com'},
                    {firstName: 'Francoise', lastName: 'Frere', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com'},
                    {firstName: 'Blandine', lastName: 'Faivre', birthDate: new Date('1987-04-25'), balance: -2323.22, email: 'oufblandou@gmail.com'},
                    {firstName: 'Francoise', lastName: 'Frere', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com'},
                    {firstName: 'Blandine', lastName: 'Faivre', birthDate: new Date('1987-04-25'), balance: -2323.22, email: 'oufblandou@gmail.com'},
                    {firstName: 'Blandine', lastName: 'Faivre', birthDate: new Date('1987-04-25'), balance: -2323.22, email: 'oufblandou@gmail.com'},
                    {firstName: 'Francoise', lastName: 'Frere', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com'},
                    {firstName: 'Francoise', lastName: 'Frere', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com'},
                ]
           $scope.displayedRowCollection = [].concat($scope.rowCollection)
       

]).directive("monitoringoverview", ($templateCache, $timeout) ->
    return {
        restrict : "EA"
        template: $templateCache.get("monitoring_overview_template.html")
        link : (scope, el, attrs) ->
     
            
            
            
            scope.actual_data = [
                {firstName: 'Laurent', lastName: 'Renard', birthDate: new Date('1987-05-21'), balance: 102, email: 'whatever@gmail.com',},
                {firstName: 'Laurent', lastName: 'Renard', birthDate: new Date('1987-05-21'), balance: 102, email: 'whatever@gmail.com', special: true, hidden: true},
                {firstName: 'Blandine', lastName: 'Faivre', birthDate: new Date('1987-04-25'), balance: -2323.22, email: 'oufblandou@gmail.com'},
                {firstName: 'Blandine', lastName: 'Faivre', birthDate: new Date('1987-04-25'), balance: -2323.22, email: 'oufblandou@gmail.com', special: true, hidden: true},
                {firstName: 'Francoise', lastName: 'Frere', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com'},
                {firstName: 'Francoise', lastName: 'Frere', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com', special: true, hidden: true},
            ];
            for item in scope.actual_data
                item.expanded = false
            scope.displayed_data = [].concat(scope.actual_data)
            f = () ->
                scope.$apply(
                    scope.displayed_data.pop(0)
                )
                console.log "now", scope.actual_data
                $timeout(f, 1000)
            #$timeout(f, 1000)
            scope.toggled = (row) ->
                index = scope.displayed_data.indexOf(row)
                entry = scope.displayed_data[index+1]
                entry.hidden = !entry.hidden
                
            scope.fun = (row) ->
                index = scope.displayed_data.indexOf(row)
                index++;
                scope.displayed_data.splice(index, 0, {firstName: 'Child', lastName: 'Child', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com'})
                scope.displayed_data.splice(index, 0, {firstName: 'Child', lastName: 'Child', birthDate: new Date('1955-08-27'), balance: 42343, email: 'raymondef@gmail.com'})        
                
}).directive('customSearch', () ->
    return {
      restrict:'E',
      require:'^stTable',
      template: """
      <select ng-model="filterValue">
      <option value="a">my a</option>
      <option value="b">my b</option>
      <option value="102">my 102</option>
    </select>
"""
      scope:true,
      link: (scope, element, attr, ctrl) ->
         tableState=ctrl.tableState();
         scope.$watch('filterValue', (value) ->
           if(value)
             tableState.search.predicateObject = {}

             console.log 'a'
             console.log ctrl
             ctrl.search(value, '');
             #if(value=='a')
             #  ctrl.search('a', 'firstName');
             #else 
             #  ctrl.search('b', 'firstName')
               
             console.log ctrl
             
             
           
         )
      
}).run(($templateCache) ->
    $templateCache.put("monitoring_overview_template.html", monitoring_overview_template)
    $templateCache.put("mytemplate.html", """
{% verbatim %}
 <div class="pagination" ng-if="pages.length >= 2"><ul class="pagination">
    <li><a ng-click="selectPage(1)">got to first</a> </li>
    <li ng-repeat="page in pages" ng-class="{active: page==currentPage}"><a ng-click="selectPage(page)">{{page}}</a></li>
    <li><a ng-click="selectPage(numPages)">go to last</a></li>
    </ul></div><b> Number of pages: {{pages.length}}</b>
{% endverbatim %}
""")
)


{% endinlinecoffeescript %}

</script>

