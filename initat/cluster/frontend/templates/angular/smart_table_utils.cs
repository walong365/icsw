{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

paginator_template = 
"""
    <form class="form-inline">
        <span ng-show="pages.length > 0">
            <div class="form-group">
                <!-- small pager -->
                <ul class="pagination pagination-sm" ng-show="numPages > 1 && numPages < 11"  style="margin-top:0px; margin-bottom:0px;">
                    <li ng-repeat="pag_num in pages" ng-class="{active: pag_num==currentPage}">
                        <a href="#" ng-click="selectPage(pag_num)">{{ pag_num }}</a>
                    </li>
                </ul>
                <!-- large pager with back/forward buttons -->
                <ul class="pagination pagination-sm" ng-show="numPages > 1 && numPages > 10"  style="margin-top:0px; margin-bottom:0px;">
                    <li ng-class="{disabled: currentPage == 1}">
                        <a href="#" ng-click="selectPage(currentPage-1)">&laquo;</a>
                    </li>
                    <li ng-class="{disabled: currentPage == numPages}">
                        <a href="#" ng-click="selectPage(currentPage+1)">&raquo;</a>
                    </li>
                    <li ng-repeat="pag_num in pages" ng-class="{active: pag_num==currentPage}">
                        <a href="#" ng-click="selectPage(pag_num)">{{ pag_num }}</a>
                    </li>
                </ul>
            </div>
            <span ng-show="numPages > 5">
                <select class="form-control input-sm" ng-model="currentPage" ng-change="selectPage(currentPage)"
                    ng-options="idx as get_range_info(idx, stItemsByPage, numPages) for idx in [] | range:numPages"
                >
                </select>
            </span>
            <span ng-show="numPages > 1">, </span>
            <span ng-show="numPages < 6">
                showing entries {{ ((currentPage-1)  * stItemsByPage) + 1 }} to {{ currentPage  * stItemsByPage }}
            </span>
        </span>
        <span ng-show="pages.length == 0">
            no entries to show,
        </span>
        <span ng-show="true"> <!-- pagSettings.conf.modify_epp -->
            show
            <div class="form-group">
                <select class="form-control input-sm" ng-model="stItemsByPage" ng-options="value as value for value in possibleItemsByPage"></select>
            </div> per page,
        </span>
    </form>
"""

{% endverbatim %}

root = exports ? this

angular.module(
    "smart_table_utils", []
).directive('icswPagination', ($templateCache) ->
    return {
        restrict: 'EA',
        require: '^stTable',
        scope: {
            stItemsByPage: '=?',
            stDisplayedPages: '=?'
        },
        template: $templateCache.get("paginator.html")
        link: (scope, element, attrs, ctrl) ->

            scope.stItemsByPage = scope.stItemsByPage or 10
            scope.stDisplayedPages = scope.stDisplayedPages or 5

            if attrs.possibleItemsByPage
                scope.possibleItemsByPage = (parseInt(i) for i in attrs.possibleItemsByPage.split(","))
            else
                scope.possibleItemsByPage = [10,20,50,100,200,500,1000]

            scope.currentPage = 1
            scope.pages = []

            redraw = () ->
                paginationState = ctrl.tableState().pagination;
                start = 1;
                scope.currentPage = Math.floor(paginationState.start / paginationState.number) + 1

                start = Math.max(start, scope.currentPage - Math.abs(Math.floor(scope.stDisplayedPages / 2)))
                end = start + scope.stDisplayedPages

                if end > paginationState.numberOfPages
                    end = paginationState.numberOfPages + 1
                    start = Math.max(1, end - scope.stDisplayedPages)

                scope.pages = []
                scope.numPages = paginationState.numberOfPages

                for i in [start..end]
                    scope.pages.push(i)

            #//table state --> view
            scope.$watch(
                    () -> return ctrl.tableState().pagination,
                    redraw, true)

            #//scope --> table state  (--> view)
            scope.$watch('stItemsByPage', () ->
                scope.selectPage(1)
            )

            scope.$watch('stDisplayedPages', redraw)

            #//view -> table state
            scope.selectPage = (page) ->
                if (page > 0 && page <= scope.numPages) 
                    ctrl.slice((page - 1) * scope.stItemsByPage, scope.stItemsByPage);

            #//select the first page
            ctrl.slice(0, scope.stItemsByPage)
            
            scope.get_range_info = (num) =>
                num = parseInt(num)
                s_val = (num - 1 ) * scope.stItemsByPage + 1
                e_val = s_val + scope.stItemsByPage - 1
                if e_val > ctrl.getNumberOfTotalEntries()
                    e_val = ctrl.getNumberOfTotalEntries()
                return "page #{num} (#{s_val} - #{e_val})"
}).run(($templateCache) ->
    $templateCache.put("paginator.html", paginator_template)
)




{% endinlinecoffeescript %}

</script>
