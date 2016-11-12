# Copyright (C) 2015-2016 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
"""

contains command for deleting objects in background (we are the background)

"""

from __future__ import unicode_literals, print_function

import json
import time

from django.db import transaction

import initat
from initat.cluster.backbone.models import DeleteRequest
from initat.cluster.backbone.models.functions import can_delete_obj
from initat.cluster_server.modules import cs_base_class
from initat.tools import logging_tools


class handle_delete_requests(cs_base_class.icswCSServerCom):

    class Meta:
        background = True
        max_instances = 4

    def _call(self, cur_inst):
        deletions = 0
        has_reqs = True

        while has_reqs:
            # obtain a request
            with transaction.atomic():
                has_reqs = DeleteRequest.objects.all().exists()
                if has_reqs:
                    req = DeleteRequest.objects.all().first()
                    req.delete()
                else:
                    req = None

            if req is not None:
                # check if we should terminate (only if we have reqs left)
                if cur_inst.executing_process is not None:
                    # handle msgs
                    cur_inst.executing_process.step(blocking=False)
                    if not cur_inst.executing_process["run_flag"]:
                        cur_inst.log("Stopping deletions due to run_flag set to False")
                        break

                self.handle_deletion(req.obj_pk, req.model, req.delete_strategies, cur_inst)
                deletions += 1

        result = "Deleted {}".format(logging_tools.get_plural("object", deletions))
        cur_inst.log(result)
        cur_inst.srv_com.set_result(result)

    @staticmethod
    def handle_deletion(obj_pk, model, delete_strategies, cur_inst):
        model = getattr(initat.cluster.backbone.models, model)
        try:
            obj_to_delete = model.objects.get(pk=obj_pk)
        except model.DoesNotExist:
            cur_inst.log("Object with pk {} from model {} does not exist any more".format(obj_pk, model))
        else:
            cur_inst.log("Deleting {} ({}; pk:{})".format(obj_to_delete, model, obj_pk))

            start_time = time.time()
            if delete_strategies:
                # have to do elaborate deletion of references
                delete_strategy_list = json.loads(delete_strategies)

                delete_strategies = {}
                for entry in delete_strategy_list:
                    delete_strategies[(entry['model'], entry['field_name'])] = entry['selected_action']

                # get references again and apply the selected strategy for each according to delete_strategies
                can_delete_answer = can_delete_obj(obj_to_delete)
                for rel_obj in can_delete_answer.related_objects:
                    dict_key = (rel_obj.model._meta.object_name, rel_obj.field.name)
                    strat = delete_strategies.get(dict_key, None)
                    if strat == "set null":
                        cur_inst.log("set null on {} ".format(rel_obj))
                        for db_obj in rel_obj.ref_list:
                            setattr(db_obj, rel_obj.field.name, None)
                            db_obj.save()
                    elif strat == "delete cascade":
                        for db_obj in rel_obj.ref_list:
                            cur_inst.log("delete cascade for {} ({})".format(db_obj, rel_obj))
                            db_obj.delete()
                    elif strat == "delete object":
                        cur_inst.log("delete object on {}".format(rel_obj))
                        for db_obj in rel_obj.ref_list:
                            db_obj.delete()
                    else:
                        raise ValueError("Invalid strategy for {}: {}; available strategies: {}".format(
                            dict_key, strat, delete_strategies
                        ))

                cur_inst.log("all refs have been deleted")
                can_delete_answer_after = can_delete_obj(obj_to_delete)
                if can_delete_answer_after:
                    # all references cleared
                    obj_to_delete.delete()
                else:
                    cur_inst.log(can_delete_answer_after.msg)

            else:
                # can delete obj right away
                obj_to_delete.delete()

            cur_inst.log("Deletion finished in {} seconds".format(time.time() - start_time))
