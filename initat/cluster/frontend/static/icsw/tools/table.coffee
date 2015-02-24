angular.module(
    "icsw.tools.table", [
        "restangular"
    ]
).directive('icswToolsPagination', ["$templateCache", ($templateCache) ->
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
    }
]).directive('icswToolsRestTable', ["Restangular", "$parse", "$injector", "$compile", "$templateCache", "$modal", "icswTools", "icswToolsSimpleModalService", "toaster", "$timeout",
    (Restangular, $parse, $injector, $compile, $templateCache, $modal, icswTools, icswToolsSimpleModalService, toaster, $timeout) ->
        return {
            restrict: 'EA'
            scope: true
            link: (scope, element, attrs) ->
                scope.config_service = $injector.get(attrs.configService)

                scope.config_service.use_modal ?= true

                if scope.config_service.init_fn?
                    scope.config_service.init_fn(scope)

                scope.data_received = (new_data) ->
                    list = $parse(attrs.targetList)(scope)
                    # behold, the recommended javascript implementation of list.clear():
                    list.length = 0
                    # also the code below does not work if we execute it immediately, but this works:
                    fn = () ->
                        for entry in new_data
                            list.push(entry)

                    $timeout(fn, 0)

                    # NOTE: this also makes the watch below work, see below before changing this


                if scope.config_service.rest_url?
                    scope.rest = Restangular.all(scope.config_service.rest_url.slice(1))

                    scope.reload = () ->

                        options = if scope.config_service.rest_options? then scope.config_service.rest_options else {}
                        scope.rest.getList(options).then(scope.data_received)

                    scope.reload()

                if scope.config_service.rest_handle?
                    scope.rest = scope.config_service.rest_handle

                    scope.reload = () ->

                        options = if scope.config_service.rest_options? then scope.config_service.rest_options else {}
                        scope.rest.getList(options).then(scope.data_received)

                if scope.rest?
                    # NOTE: watching on restangular does not work. if $object gets filled up, there is NO call.
                    # therefore we watch on the length, which works. this also gets called on reload because of the
                    # way it is implemented above.
                    scope.$watch(
                        () -> return scope.rest.length
                        (new_data) ->
                            # this should be called when the data is here, but we can't control that
                            if scope.config_service.after_reload
                                scope.config_service.after_reload(scope)
                    )

                $parse(attrs.targetList).assign(scope, scope.rest)

                # interface functions to use in directive body
                scope.edit = (event, obj) ->
                    scope.pre_edit_obj = angular.copy(obj)
                    scope.create_or_edit(event, false, obj)
                scope.create = (event) ->
                    if typeof(scope.config_service.new_object) == "function"
                        scope.new_obj = scope.config_service.new_object()
                    else
                        scope.new_obj = scope.config_service.new_object
                    scope.create_or_edit(event, true, scope.new_obj)
                scope.create_or_edit = (event, create_or_edit, obj) ->
                    scope.edit_obj = obj
                    scope.create_mode = create_or_edit
                    if scope.fn and scope.fn.create_or_edit
                        scope.fn.create_or_edit(scope, scope.create_mode, obj)
                    if scope.config_service.use_modal
                        scope.edit_div = $compile($templateCache.get(scope.config_service.edit_template))(scope)
                        scope.my_modal = BootstrapDialog.show
                            message: scope.edit_div
                            draggable: true
                            size: BootstrapDialog.SIZE_WIDE
                            closable: true
                            closeByBackdrop: false
                            onhidden: () =>
                                scope.modal_active = false
                            onshow: (modal) =>
                                height = $(window).height() - 100
                                modal.getModal().find(".modal-body").css("max-height", height)
                            onshown: () =>
                                scope.modal_active = true
                    else
                        scope.modal_active = true
                scope.modify = () ->
                    if not scope.form.$invalid
                        if scope.create_mode
                            scope.rest.post(scope.new_obj).then((new_data) ->
                                scope.rest.push(new_data)
                                scope.close_modal()
                                if scope.config_service.object_created
                                    scope.config_service.object_created(scope.new_obj, new_data, scope)
                            )
                        else
                            scope.edit_obj.put().then(
                                (data) ->
                                    icswTools.handle_reset(data, scope.rest, scope.edit_obj.idx)
                                    if scope.config_service.object_modified
                                        scope.config_service.object_modified(scope.edit_obj, data, scope)
                                    scope.close_modal()
                                (resp) -> icswTools.handle_reset(resp.data, scope.rest, scope.edit_obj.idx)
                            )
                    else
                        toaster.pop("warning", "", "form validation problem")
                scope.form_error = (field_name) ->
                    # temporary fix, FIXME
                    # scope.form should never be undefined
                    if scope.form?
                        if scope.form[field_name].$valid
                            return ""
                        else
                            return "has-error"
                    else
                        return ""
                scope.hide_modal = () ->
                    # hides dummy modal
                    if not scope.fn.use_modal and scope.modal_active
                        scope.modal_active = false
                scope.close_modal = () ->
                    if scope.config_service.use_modal
                        scope.my_modal.close()
                    scope.modal_active = false
                    if scope.fn and scope.fn.modal_closed
                        scope.fn.modal_closed(scope)
                        if scope.config_settings.use_modal
                            try
                                # fixme, call digest cycle and ignore if cycle is already running
                                scope.$digest()
                            catch exc
                scope.get_action_string = () ->
                    return if scope.create_mode then "Create" else "Modify"
                scope.delete = (obj) ->
                    icswToolsSimpleModalService(scope.config_service.delete_confirm_str(obj)).then(
                        () ->
                            # check for a pre_delete function
                            if scope.config_service.pre_delete
                                scope.config_service.pre_delete(obj)
                            if scope.config_service.delete
                                scope.config_service.delete(scope, obj)
                            else
                                obj.remove().then(
                                    (resp) ->
                                        toaster.pop("success", "", "deleted instance")
                                        icswTools.remove_by_idx($parse(attrs.targetList)(scope), obj.idx)
                                        if scope.config_service.post_delete
                                            scope.config_service.post_delete(scope, obj)
                                )
                    )
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
         link: (scope, element, attrs) ->
             scope.columns = attrs.columns.split(' ')
             scope.show_column = {}
             for col in scope.columns
                scope.show_column[col] = true
     }
)
