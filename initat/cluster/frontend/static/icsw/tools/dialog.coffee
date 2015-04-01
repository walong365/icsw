angular.module(
    "icsw.tools.dialog",
    [
        "icsw.tools.button",
    ]
).service('icswDialogDeleteObjects',
    ['icswParseXMLResponseService', 'icswCallAjaxService', 'icswToolsSimpleModalService', 'ICSW_URLS', '$rootScope',
    '$compile', '$templateCache', 'toaster', 'blockUI', '$interval',
    (icswParseXMLResponseService, icswCallAjaxService, icswToolsSimpleModalService, ICSW_URLS, $rootScope,
    $compile, $templateCache, toaster, blockUI, $interval) ->
        # Ask whether to delete object, then deal with references (show popup querying user for actions)

        return (objects_to_delete, model, after_delete) ->
            # objects_to_delete: list of things which have 'idx' and 'name'
            # model: name in initat.cluster.backbone.models which contains the objects
            # after_delete: called after deletions have occurred, use to refresh your data

            actual_delete = (objs_to_delete, async) ->
                if async
                    toaster.pop("info", "", "Deleting #{objs_to_delete.length} objects in background")
                else
                    blockUI.start("Deleting #{objs_to_delete.length} objects")

                del_pks = []
                for obj in objs_to_delete
                    if angular.isNumber(obj)
                        obj_pk = obj
                        delete_strategies = undefined
                    else
                        obj_pk = obj.obj_pk
                        delete_strategies = JSON.stringify(obj.delete_strategies)

                    del_pks.push(obj_pk)

                    icswCallAjaxService
                        url: ICSW_URLS.BASE_ADD_DELETE_REQUEST
                        data: {
                            model: model
                            obj_pk: obj_pk
                            delete_strategies: delete_strategies
                        }
                        success: (xml) ->
                            icswParseXMLResponseService(xml)


                last_msg = undefined
                interval_promise = null
                interval_promise = $interval(
                    () ->
                        icswCallAjaxService
                            url: ICSW_URLS.BASE_CHECK_DELETION_STATUS
                            data:
                                model: model
                                obj_pks: JSON.stringify(del_pks)
                            success: (xml) ->
                                if icswParseXMLResponseService(xml)
                                    # handle msg
                                    msg = $(xml).find("value[name='msg']").text()
                                    if async
                                        if last_msg != msg
                                            toaster.pop("info", "", msg)
                                    else
                                        blockUI.message(msg)

                                    last_msg = msg

                                    # check if we are done
                                    num_remaining = parseInt($(xml).find("value[name='num_remaining']").text())
                                    if num_remaining == 0
                                        if after_delete?
                                            after_delete()

                                        if !async
                                            blockUI.stop()

                                        $interval.cancel(interval_promise)
                    1500
                )

                #        # close if all objects are gone now
                #            if Object.keys(related_objects).length == 0
                #                child_scope.modal.close()


#            # recursive asynchronous delete fun
#            actual_delete = (deletable_objects, num_all, done_callback) ->
#                if deletable_objects.length
#                    to_del = deletable_objects.pop(0)
#                    icswCallAjaxService
#                        url: ICSW_URLS.BASE_DO_DELETE_OBJECT
#                        data: {
#                            model: model
#                            obj_pk: to_del
#                        }
#                        timeout: 1200000  # 20 minutes: it would be bad to stop a deletion in process
#                        success: (xml) ->
#                            if icswParseXMLResponseService(xml)
#                                toaster.pop("info", "", "Deleted #{num_all - deletable_objects.length} of #{num_all} objects")
#                                if after_delete?
#                                    after_delete()
#                                # recurse, elem has been removed from list already
#                                actual_delete(deletable_objects, num_all, done_callback)
#                else
#                    if done_callback
#                        done_callback()
#

            show_delete_dialog = (related_objects, deletable_objects) ->
                # shows dialog if objs to delete have hard references
                # related_objs is dict { obj_pk : [ related_obj_info ] }
                # deletable_objects is [obj_pk]
                child_scope = $rootScope.$new()

                child_scope.async_delete = true
                child_scope.related_objects = related_objects
                child_scope.deletable_objects = deletable_objects

                child_scope.delete_deletable_dict = {}
                for pk in deletable_objects
                    child_scope.delete_deletable_dict[pk] = true
                child_scope.delete_deletable_action = () ->
                    to_delete = []
                    for k, v of child_scope.delete_deletable_dict
                        if v
                            k_int = parseInt(k)  # yay, javascript!
                            to_delete.push(k_int)
                            # remove from gui
                            _.remove(child_scope.deletable_objects, (elem) -> return elem == k_int)
                            delete child_scope.delete_deletable_dict[k_int]

                    actual_delete(to_delete, child_scope.async_delete)


                child_scope.all_actions_defined = (obj_pk) ->
                    return _.all(related_objects[obj_pk], (elem) -> return elem.selected_action?)
                child_scope.force_delete = (obj_pk) ->
                    delete_strategies = []
                    # collect data from gui
                    for entry in related_objects[obj_pk]
                        strat = {}
                        for key in ['field_name', 'model', 'selected_action']
                            strat[key] = entry[key]

                        delete_strategies.push(strat)

                    actual_delete(
                        [{obj_pk: obj_pk, delete_strategies: delete_strategies}]
                        child_scope.async_delete
                    )

                    delete related_objects[obj_pk]

#                    icswCallAjaxService
#                        url: ICSW_URLS.BASE_FORCE_DELETE_OBJECT
#                        data: {
#                            model: model
#                            obj_pk: obj_pk
#                            delete_strategies: JSON.stringify(delete_strategies)
#                        }
#                        success: (xml) ->
#                            if icswParseXMLResponseService(xml)
#                                if after_delete?
#                                    after_delete()
#                                toaster.pop("info", "", "Deleted 1 object")


                child_scope.get_object_by_idx = (idx) ->
                    idx = parseInt(idx)
                    return _.find(objects_to_delete, (elem) -> return elem.idx == idx)
                child_scope.is_empty_object = (obj) -> return Object.keys(obj).length == 0
                edit_div = $compile($templateCache.get("icsw.dialog.delete_popup"))(child_scope)
                edit_div.on("$destroy", () ->
                    child_scope.$destroy()
                )
                modal = BootstrapDialog.show
                    title: "Delete"
                    message: edit_div
                    draggable: true
                    closable: true
                    closeByBackdrop: false
                    size: BootstrapDialog.SIZE_WIDE
                    type: BootstrapDialog.TYPE_DANGER
                    onshow: (modal) =>
                        height = $(window).height() - 100
                        modal.getModal().find(".modal-body").css("max-height", height)
                child_scope.modal = modal


            try_delete = () ->
                objects_string = if objects_to_delete.length == 1 then objects_to_delete[0].name else objects_to_delete.length+" objects"
                #icswToolsSimpleModalService("Really delete #{ objects_string }?").then(() ->
                icswCallAjaxService
                    url: ICSW_URLS.BASE_CHECK_DELETE_OBJECT
                    data: {
                        model: model
                        obj_pks: JSON.stringify((obj.idx for obj in objects_to_delete))
                    }
                    success: (xml) ->
                        if icswParseXMLResponseService(xml)
                            related_objects = JSON.parse($(xml).find("value[name='related_objects']").text())
                            deletable_objects = JSON.parse($(xml).find("value[name='deletable_objects']").text())

                            # related objects contains info about undeletable objs,
                            # deletable_objs is just a list of deletable objects

                            # related_objs is dict { obj_pk : [ related_obj_info ] }

                            for k, ref_list of related_objects
                                for ref in ref_list
                                    ref.actions = []
                                    # only have default action if it is a "safe" one
                                    if ref.null
                                        ref.actions.push('set null')
                                        ref.selected_action = ref.actions[0]

                                    if ref.objects.num_refs_of_refs == 0
                                        ref.actions.push('delete object')
                                        if ! ref.selected_action?
                                            ref.selected_action = ref.actions[0]
                                    else
                                        ref.actions.push('delete cascade')

                            show_delete_dialog(related_objects, deletable_objects)



            try_delete()
])
