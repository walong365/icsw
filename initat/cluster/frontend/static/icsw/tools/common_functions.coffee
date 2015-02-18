
class angular_edit_mixin
    constructor : (@scope, @templateCache, @compile, @modal, @Restangular, @q, @name) ->
        @use_modal = true
        @new_object_at_tail = true
        @use_promise = false
        @put_parameters = {}
        @min_width = "600px"
        @change_signal = undefined
        @title = "Modal"
    create : (event) =>
        if @new_object
            @scope.new_obj = @new_object(@scope)
        else
            @scope.new_obj = {}
        return @create_or_edit(event, true, @scope.new_obj)
    send_change_signal : () =>
        if @change_signal
            @scope.$emit(@change_signal)
    edit : (obj, event) =>
        @create_or_edit(event, false, obj)
    modify_data_before_put: (data) =>
        # dummy, override in app
    modify_data_after_post: (data) =>
        # dummy, override in app
    create_or_edit : (event, create_or_edit, obj) =>
        @closed = false
        @scope._edit_obj = obj
        @scope.pre_edit_obj = angular.copy(obj)
        @scope.create_mode = create_or_edit
        @scope.cur_edit = @
        if not @scope.create_mode and @modify_rest_url
            @Restangular.restangularizeElement(null, @scope._edit_obj, @modify_rest_url)
        @scope.action_string = if @scope.create_mode then "Create" else "Modify"
        if @use_promise
            @_prom = @q.defer()
        if @use_modal
            @child_scope = @scope.$new(false, @scope)
            @edit_div = @compile(@templateCache.get(if @scope.create_mode then @create_template else @edit_template))(@child_scope)
            @edit_div.on("$destroy", () =>
                _scope= angular.element(@edit_div[0]).scope()
                #console.log "DEST", @edit_div[0], @scope, @child_scope
                @child_scope.$destroy()
                return null
            )
            @my_modal = BootstrapDialog.show
                message: @edit_div
                draggable: true
                size: BootstrapDialog.SIZE_WIDE
                title: @title
                closable: true
                closeByBackdrop: false
                cssClass: @cssClass
                onhidden: () =>
                    @scope.modal_active = false
                onshow: (modal) =>
                    height = $(window).height() - 100
                    modal.getModal().find(".modal-body").css("max-height", height)
                onshown: () =>
                    @scope.modal_active = true
            #@edit_div.simplemodal
            #    #opacity      : 50
            #    position     : [event.clientY - 50, event.clientX - 50]
            #    minWidth : @min_width
            #    #autoResize   : true
            #    #autoPosition : true
            #    onShow: (dialog) =>
            #        dialog.container.draggable()
            #        $("#simplemodal-container").css("height", "auto")
            #        @_modal_close_ok = false
            #        @scope.modal_active = true
            #        # set active angular edit mixin to @name to distinguish between different mixins
            #        @scope.active_aem = @name
            #    onClose: (dialog) =>
            #        @close_modal()
        else
            @child_scope = @scope
            @scope.modal_active = true
            @scope.active_aem = @name
        if @use_promise
            return @_prom.promise
    close_modal : () =>
        if @use_modal
            @my_modal.close()
        #console.log scope.pre_edit_obj.pnum, scope._edit_obj.pnum
        if @scope.modal_active
            #console.log "*", @_modal_close_ok, @scope.pre_edit_obj
            if not @_modal_close_ok and not @scope.create_mode
                # not working right now, hm ...
                true
                #@scope._edit_obj = angular.copy(@scope.pre_edit_obj)
                #console.log @scope._edit_obj.pnum, @scope.pre_edit_obj.pnum
                #@scope._edit_obj.pnum = 99
                #console.log @scope._edit_obj, @scope.pre_edit_obj
        @scope.modal_active = false
        @scope.active_aem = undefined
        if @edit_div
            @edit_div.remove()
        if @use_promise and not @closed
            # added to catch close events
            if @_prom
                return @_prom.resolve(false)
        return null
    form_error : (field_name) =>
        # hm, hack. needed in partition_table.cs / part_overview.html
        if field_name of @child_scope.form
            if @child_scope.form[field_name].$valid
                return ""
            else
                return "has-error"
    modify : () ->
        # FIXME, to be moved to icswTools call
        handle_reset = (data, e_list, idx) ->
            # used to reset form fields when requested by server reply
            if data._reset_list
                if idx == null
                    # special case: e_list is the element to modify
                    scope_obj = e_list
                else
                    scope_obj = (entry for key, entry of e_list when key.match(/\d+/) and entry.idx == idx)[0]
                $(data._reset_list).each (idx, entry) ->
                    scope_obj[entry[0]] = entry[1]
                delete data._reset_list
        @closed = true
        if not @child_scope.form.$invalid
            if @scope.create_mode
                @create_rest_url.post(@scope.new_obj).then(
                    (new_data) =>
                        if @create_list
                            if @new_object_at_tail
                                @create_list.push(new_data)
                            else
                                @create_list.splice(0, 0, new_data)
                        @modify_data_after_post(new_data)
                        @close_modal()
                        @_modal_close_ok = true
                        if @use_promise
                            return @_prom.resolve(new_data)
                        else
                            @send_change_signal()       
                    () ->        
                        if @use_promise
                            return @_prom.resolve(false)
                )
            else
                @modify_data_before_put(@scope._edit_obj)
                @scope._edit_obj.put(@put_parameters).then(
                    (data) =>
                        handle_reset(data, @scope._edit_obj, null)
                        @_modal_close_ok = true
                        @close_modal()
                        if @use_promise
                            return @_prom.resolve(data)
                        else
                            @send_change_signal()                
                    (resp) =>
                        if @use_promise
                            return @_prom.resolve(false)
                        else
                            handle_reset(resp.data, @scope._edit_obj, null)
                )
        else
            # move to toaster, FIXME, todo
            console.log "form validation problem"
    modal_ctrl : ["$scope", "$modalInstance", "question", ($scope, $modalInstance, question) ->
        $scope.question = question
        $scope.ok = () ->
            $modalInstance.close(true)
        $scope.cancel = () ->
            $modalInstance.dismiss("cancel")
    ]
    delete_obj : (obj) =>
        if @use_promise
           ret = @q.defer()
        c_modal = @modal.open
            template : @templateCache.get("icsw.tools.simple.modal")
            controller : @modal_ctrl
            backdrop : "static"
            resolve :
                question : () =>
                    if @delete_confirm_str
                        return @delete_confirm_str(obj)
                    else
                        return "Really delete object ?"
        c_modal.result.then(
            () =>
                # FIXME, to be moved to icswTools call
                remove_by_idx = (in_array, idx) ->
                    for c_idx, val of in_array
                        if val.idx == idx
                            c_idx = parseInt(c_idx)
                            rest = in_array.slice(c_idx + 1 || in_array.length)
                            in_array.length = if c_idx < 0 then in_array.length + c_idx else c_idx
                            in_array.push.apply(in_array, rest)
                            break

                # add restangular elements
                if not obj.addRestangularMethod and @modify_rest_url
                    @Restangular.restangularizeElement(null, obj, @modify_rest_url)
                obj.remove().then(
                    (resp) =>
                        # todo, fixme, move to toaster
                        console.log "deleted instance"
                        if @delete_list
                            remove_by_idx(@delete_list, obj.idx)
                        @close_modal()
                        if @use_promise
                            return ret.resolve(true)
                        else
                            @send_change_signal()
                    () =>
                        if @use_promise
                            return ret.resolve(false)
                )
            () =>
                if @use_promise
                    return ret.resolve(false)
        )
        if @use_promise
            return ret.promise

class angular_modal_mixin
    constructor : (@scope, @templateCache, @compile, @q, @title) ->
        @cssClass = ""
    edit : (obj, event) =>
        @scope._edit_obj = obj
        @scope.cur_edit = @
        @_prom = @q.defer()
        @edit_div = @compile(@templateCache.get(@template))(@scope)
        @my_modal = BootstrapDialog.show
            message: @edit_div
            draggable: true
            size: BootstrapDialog.SIZE_WIDE
            title: @title
            closable: true
            cssClass: @cssClass
            closeByBackdrop: false
            onhidden: () =>
                @scope.modal_active = false
            onshow: (modal) =>
                height = $(window).height() - 100
                modal.getModal().find(".modal-body").css("max-height", height)
            onshown: () =>
                @scope.modal_active = true
            #buttons: [{
            #    label: 'close',
            #    cssClass: "btn-danger"
            #    action: (dialog) ->
            #        dialog.close()
            #    }]
        return @_prom.promise
    close_modal : () =>
        @my_modal.close()
    form_error : (field_name) =>
        if @scope.form[field_name].$valid
            return ""
        else
            return "has-error"
    modify : () ->
        if not @scope.form.$invalid
            @close_modal()
            return @_prom.resolve(@scope._edit_obj)
        else
            # fixme, todo, move to toaster
            console.log "form validation problem"

reload_sidebar_tree = (pk_list) ->
    sidebar_div = $("div[id='icsw.sidebar'] > div[id='sidebar-wrapper']")
    # sidebar found ?
    if sidebar_div.length
        scope = angular.element(sidebar_div[0]).scope()
        scope.$apply(() ->
            scope.reload(pk_list)
        )

root = exports ? this
root.angular_edit_mixin = angular_edit_mixin
root.angular_modal_mixin = angular_modal_mixin
root.reload_sidebar_tree = reload_sidebar_tree

