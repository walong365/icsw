
angular.module(
    "icsw.tools.table", []
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

            scope.Math = Math;
            # this is not nice but only needed for a minor thing (see template above)
            # the problem is that we can't access the scope of the outer directive as the st-table directive overwrites the scope
            scope.table_controller = ctrl;

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

                for i in [start..(end-1)]
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
}).run(() ->
)


