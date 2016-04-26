# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

angular.module(
    "icsw.tools.table", [
        "restangular"
    ]
).directive('icswToolsTableFilteredElements', () ->
    return {
        restrict: 'E'
        require: '^stTable',
        scope: {}
        template: "{{num_filtered}}"
        link: (scope, element, attrs, ctrl) ->
            scope.$watch(
                () -> return ctrl.getFilteredCollection().length
                (new_val) -> scope.num_filtered = new_val
            )
    }
).directive('icswToolsTableLeakFiltered', ["$parse", ($parse) ->
    return {
        restrict: 'EA'
        require: '^stTable',
        link: (scope, element, attrs, ctrl) ->
            scope.$watch(
                ctrl.getFilteredCollection
                (new_val) ->
                    $parse(attrs.icswToolsTableLeakFiltered).assign(scope, new_val)
            )
    }
]).directive('icswToolsTableNumSelected', ["$parse", ($parse) ->
    return {
        restrict: 'EA'
        require: '^stTable',
        link: (scope, element, attrs, ctrl) ->
            scope.$watch(
                ctrl.getNumberOfSelectedEntries
                (new_val) ->
                    $parse(attrs.icswToolsTableNumSelected).assign(scope, new_val)
            )
    }
]).directive('icswToolsPagination', ["$templateCache", "$parse", ($templateCache, $parse) ->
    return {
        restrict: 'EA'
        require: '^stTable'
        scope: {
            stItemsByPage: '=?'
            stDisplayedPages: '=?'
            noNumberOfElements: '=?'
        }
        template: $templateCache.get("icsw.tools.paginator")
        link: (scope, element, attrs, ctrl) ->

            scope.stItemsByPage = scope.stItemsByPage or 10
            scope.stDisplayedPages = scope.stDisplayedPages or 5
            scope.noNumberOfElements = scope.noNumberOfElements or false
            scope.Math = Math
            # this is not nice but only needed for a minor thing (see template above)
            # the problem is that we can't access the scope of the outer directive as the st-table directive overwrites the scope
            scope.table_controller = ctrl

            if attrs.possibleItemsByPage
                scope.possibleItemsByPage = (parseInt(i) for i in attrs.possibleItemsByPage.split(","))
            else
                scope.possibleItemsByPage = [10, 20, 50, 100, 200, 500, 1000]

            scope.currentPage = 1
            scope.pages = []

            redraw = () ->
                paginationState = ctrl.tableState().pagination
                start = 1
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

            # table state --> view
            scope.$watch(
                () -> return ctrl.tableState().pagination
                redraw
                true
            )

            # scope --> table state  (--> view)
            scope.$watch('stItemsByPage', (new_val) ->
                scope.selectPage(1)
            )

            scope.$watch('stDisplayedPages', redraw)

            # view -> table state
            scope.selectPage = (page) ->
                if (page > 0 && page <= scope.numPages) 
                    ctrl.slice((page - 1) * scope.stItemsByPage, scope.stItemsByPage)

            # select the first page
            ctrl.slice(0, scope.stItemsByPage)
            
            scope.get_range_info = (num) =>
                num = parseInt(num)
                s_val = (num - 1 ) * scope.stItemsByPage + 1
                e_val = s_val + scope.stItemsByPage - 1
                # removed because getNumberOfTotalEntries is no longer defined in newer st-table versions
                # if !scope.noNumberOfElements and e_val > ctrl.getNumberOfTotalEntries()
                #    e_val = ctrl.getNumberOfTotalEntries()
                return "page #{num} (#{s_val} - #{e_val})"
    }
]).directive("icswToolsRestTableNew",
[
    "Restangular", "$parse", "$injector", "$compile", "$templateCache", "icswTools",
    "icswToolsSimpleModalService", "toaster", "$timeout",
(
    Restangular, $parse, $injector, $compile, $templateCache, icswTools,
    icswToolsSimpleModalService, toaster, $timeout
) ->
    return {
        restrict: 'EA'
        scope: true
        link: (scope, element, attrs) ->
            scope.config_service = $injector.get(attrs.configService)
            if attrs.icswConfigObject?
                scope.icswConfigObject = scope.$eval(attrs.icswConfigObject)
            else
                scope.icswConfigObject = undefined

            # scope.config_service.use_modal ?= true

            if scope.config_service.many_delete?
                scope.many_delete = scope.config_service.many_delete
            else
                scope.many_delete = false

            scope.data_received = (new_data) ->
                $parse(attrs.targetList).assign(scope, new_data)
                # behold, the recommended javascript implementation of list.clear():
                # also the code below does not work if we execute it immediately, but this works:
                # fn = () ->
                #    if scope.config_service.post_reload_func?
                #        scope.config_service.post_reload_func()

                # $timeout(fn, 0)
                # NOTE: this also makes the watch below work, see below before changing this


            if scope.config_service.init_fn?
                scope.config_service.init_fn(scope)

            scope.config_service.fetch(scope).then(
                (list) ->
                    scope.data_received(list)
            )

            # interface functions to use in directive body
            scope.edit = (event, obj) ->
                scope.create_or_edit(event, false, obj)

            scope.create = (event, obj) ->
                scope.create_or_edit(event, true, obj)

            scope.create_or_edit = (event, create, obj_or_parent) ->
                scope.config_service.create_or_edit(scope, event, create, obj_or_parent)

            scope.special_fn = (event, fn_name, obj, data) ->
                # for non-specific functions
                scope.config_service.special_fn(scope, event, fn_name, obj, data)

            scope.form_error = (field_name) ->
                # temporary fix, FIXME
                # scope.form should never be undefined
                if scope.form_data?
                    if scope.form_data[field_name]?
                        if scope.form_data[field_name].$valid
                            return ""
                        else
                            return "has-error"
                    else
                        return ""
                else
                    return ""

            scope.delete = ($event, obj) ->
                if $event
                    $event.stopPropagation()
                scope.config_service.delete(scope, $event, obj)
    }
]).directive('icswToolsShowHideColumns', () ->
    return {
        restrict: 'EA'
        template: """
Show/Hide columns: <div class="btn-group btn-group-xs">
    <input type="button" ng-repeat="entry in columns" ng-attr-title="show/hide columns {{entry}}" ng-value="entry"
        ng-class="show_column[entry] && 'btn btn-success' || 'btn'" ng-click="show_column[entry] = ! show_column[entry]"></input>
</div>
"""
        scope: false
        link: (scope, element, attrs) ->
            scope.a = attrs
            if attrs.createShowColumn
                # NOTE: this object can easily end up in the wrong scope
                #       set this attribute if you know what you are doing, or else create the object yourself in your scope
                scope.show_column = {}


            set_new_columns = (new_columns) ->
                for k in Object.keys(scope.show_column)
                    if k not in new_columns
                        delete scope.show_column[k]

                scope.columns = new_columns
                for col in scope.columns
                    scope.show_column[col] = true

            scope.$watch(
                () -> attrs.columnsList
                (new_val) ->
                    if new_val? && new_val
                        set_new_columns(JSON.parse(new_val))
            )

            scope.$watch(
                () -> attrs.columns  # watch on attribute doesn't work
                (new_val) ->
                    if new_val?
                        set_new_columns(new_val.split(' '))

            )
     }
)
