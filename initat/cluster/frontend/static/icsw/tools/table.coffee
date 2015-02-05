
angular.module(
    "icsw.tools.table", ["restangular"]
).directive('icswToolsPagination', ($templateCache) ->
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
).directive('icswToolsRestTable', (Restangular, $parse, $injector, $compile, $templateCache, $modal) ->
    return {
        restrict: 'EA'
        scope: true
        link: (scope, element, attrs) ->
            scope.config_service = $injector.get(attrs.configService)

            scope.config_service.use_modal ?= true

            if scope.config_service.init_fn?
                scope.config_service.init_fn(scope)
            scope.data_received = (data) ->
                $parse(attrs.targetList).assign(scope, data)
                if scope.config_service.after_reload
                    scope.config_service.after_reload(scope)

            if scope.config_service.rest_url?
                $parse(attrs.targetList).assign(scope, [])
                scope.rest = Restangular.all(scope.config_service.rest_url.slice(1))

                scope.reload = () ->
                    scope.rest.getList().then(scope.data_received)

                scope.reload()

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
                    scope.edit_div.simplemodal
                        #opacity      : 50
                        position     : [event.clientY - 50, event.clientX - 50]
                        #autoResize   : true
                        #autoPosition : true
                        onShow: (dialog) =>
                            dialog.container.draggable()
                            $("#simplemodal-container").css("height", "auto")
                            scope.modal_active = true
                        onClose: (dialog) =>
                            scope.close_modal()
                else
                    scope.modal_active = true
            scope.modify = () ->
                if not scope.form.$invalid
                    if scope.create_mode
                        scope.rest.post(scope.new_obj).then((new_data) ->
                            scope.entries.push(new_data)
                            scope.close_modal()
                            if scope.config_service.object_created
                                scope.config_service.object_created(scope.new_obj, new_data, scope)
                        )
                    else
                        scope.edit_obj.put().then(
                            (data) ->
                                handle_reset(data, scope.entries, scope.edit_obj.idx)
                                if scope.config_service.object_modified
                                    scope.config_service.object_modified(scope.edit_obj, data, scope)
                                scope.close_modal()
                            (resp) -> handle_reset(resp.data, scope.entries, scope.edit_obj.idx)
                        )
                else
                    noty
                        text : "form validation problem"
                        type : "warning"
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
                    $.simplemodal.close()
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
                c_modal = $modal.open
                    template : $templateCache.get("simple_confirm.html")
                    controller : simple_modal_ctrl
                    backdrop : "static"
                    resolve :
                        question : () ->
                            return scope.config_service.delete_confirm_str(obj)
                c_modal.result.then(
                    () ->
                        obj.remove().then((resp) ->
                            noty
                                text : "deleted instance"
                            remove_by_idx($parse(attrs.targetList)(scope), obj.idx)
                            if scope.config_service.post_delete
                                scope.config_service.post_delete(scope, obj)
                        )
                )
    }
)
