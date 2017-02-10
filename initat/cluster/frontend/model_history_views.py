# Copyright (C) 2015-2017 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of icsw-server-server
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
# -*- coding: utf-8 -*-
#

import itertools
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.utils.decorators import method_decorator
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response

from initat.cluster.backbone.models import device
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.frontend.rest_views import rest_logging
from initat.tools import server_mixins, logging_tools

logger = logging.getLogger("cluster.history")


class DummyLogger(object):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        logger.log(log_level, "[DL] {}".format(what))


class get_models_with_history(RetrieveAPIView):
    @method_decorator(login_required)
    @rest_logging
    def get(self, request, *args, **kwargs):
        from initat.cluster.backbone.models.model_history import icsw_register
        return Response(
            {
                model.__name__: model._meta.verbose_name for model in icsw_register.REGISTERED_MODELS
            }
        )


class DeletedObjectsCache(dict):
    def __missing__(self, target_model):
        from reversion.models import Version
        value = {entry.pk: entry for entry in Version.objects.get_deleted(target_model)}
        self[target_model] = value
        return value


class get_historical_data(ListAPIView):
    # noinspection PyUnresolvedReferences
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        from django.db.models import ForeignKey
        from reversion.models import Version

        from initat.cluster.frontend.ext.diff_match_patch import diff_match_patch
        from initat.cluster.backbone.models.model_history import icsw_deletion_record, icsw_register

        model_name = request.GET['model']
        # try currently registered models
        try:
            model = [i for i in icsw_register.REGISTERED_MODELS if i.__name__ == model_name][0]
        except IndexError:
            model = getattr(initat.cluster.backbone.models, model_name)
        object_id = request.GET.get("object_id", None)

        def format_version(version):
            serialized_data = json.loads(version.serialized_data)[0]
            return_data = serialized_data['fields']

            if version.revision.comment == "Initial version.":
                change_type = "initial"
            else:
                change_type = None

            meta = {
                'date': version.revision.date_created,
                'user': version.revision.user_id,
                'type': change_type,
                'object_repr': version.object_repr,
                'object_id': serialized_data['pk'],
            }
            return {'meta': meta, 'data': return_data}

        def format_deletion(deletion):
            serialized_data = json.loads(deletion.serialized_data)[0]
            return_data = serialized_data['fields']

            meta = {
                'date': deletion.date,
                'user': deletion.user_id,
                'type': 'deleted',
                'object_repr': deletion.object_repr,
                'object_id': serialized_data['pk'],
            }

            return {'meta': meta, 'data': return_data}

        content_type = ContentType.objects.get_for_model(model)

        filter_dict = {'content_type': content_type}
        filter_dict_del = {"content_type": content_type}
        if object_id is not None:
            filter_dict['object_id'] = object_id
            filter_dict_del['object_id_int'] = object_id

        # get data for deletion and version (they mostly have the same fields)
        deletion_queryset = icsw_deletion_record.objects.filter(**filter_dict_del)
        # print dir(reversion.VersionAdapter)
        version_queryset = Version.objects.filter(**filter_dict).select_related('revision')

        formatted = itertools.chain(
            (format_version(ver) for ver in version_queryset),
            (format_deletion(dele) for dele in deletion_queryset)
        )

        _eco = server_mixins.EggConsumeObject(DummyLogger())
        _eco.init({"SERVICE_ENUM_NAME": icswServiceEnum.monitor_server.name})
        if model == device:
            print("FILTER")
            allowed_by_lic = (
                elem for elem in formatted if _eco.consume("history", elem["meta"]["object_id"])
            )
        else:
            allowed_by_lic = formatted

        sorted_data = sorted(allowed_by_lic, key=lambda elem: elem['meta']['date'])

        foreign_keys = {
            foreign_key.name: foreign_key for foreign_key in model._meta.concrete_model._meta.local_fields if isinstance(foreign_key, ForeignKey)
        }

        m2ms = {
            m2m.name: m2m for m2m in model._meta.concrete_model._meta.local_many_to_many if m2m.rel.through._meta.auto_created
        }
        # only serialized m2ms, which are by djangos logic the ones which are not autocreated

        deleted_objects_cache = DeletedObjectsCache()

        def resolve_reference(target_model, foreign_key_val):
            try:
                return str(target_model.objects.get(pk=foreign_key_val))
            except target_model.DoesNotExist:
                try:
                    # unicode on Version object gives the saved object repr, which we use here
                    return str(deleted_objects_cache[target_model][foreign_key_val])
                except KeyError:
                    return "untracked object"

        def get_human_readable_value(key, value):
            if value is None:
                return value
            elif key in foreign_keys:
                return resolve_reference(foreign_keys[key].rel.to, value)
            elif key in m2ms:
                return list(resolve_reference(m2ms[key].rel.to, m2m_val) for m2m_val in value)
            else:
                return value

        used_device_ids = set()

        # calc change and type info
        last_entry_by_pk = {}
        for entry in sorted_data:

            pk = entry['meta']['object_id']

            if model == device:
                used_device_ids.add(pk)

            # set missing type info
            if not entry['meta']['type']:
                if pk in last_entry_by_pk:
                    entry['meta']['type'] = 'modified'
                else:
                    entry['meta']['type'] = 'created'

            # extract change info and only transmit that
            if pk in last_entry_by_pk:
                entry['changes'] = {}
                for k in set(itertools.chain(iter(entry['data'].keys()), iter(last_entry_by_pk[pk].keys()))):
                    old = last_entry_by_pk[pk].get(k, None)
                    new = entry['data'].get(k, None)
                    if old != new:
                        patch = None
                        if isinstance(old, str) and isinstance(new, str):
                            dmp = diff_match_patch()
                            diffs = dmp.diff_main(old, new)
                            dmp.diff_cleanupSemantic(diffs)
                            patch = dmp.diff_prettyHtml(diffs)
                            patch = patch.replace('&para;', "")  # don't show para signs

                        entry['changes'][k] = {
                            'new_data_human': get_human_readable_value(k, new),
                            'old_data_human': get_human_readable_value(k, old),
                            'new_data': new,
                            'old_data': old,
                            'patch': patch,
                        }

            else:
                entry['changes'] = {
                    'full_dump': entry['data'],
                    'full_dump_human': {k: get_human_readable_value(k, v) for k, v in entry['data'].items()},
                }

            last_entry_by_pk[pk] = entry['data']
            del entry['data']

        # NOTE: entries must be in chronological, earliest first
        return Response(sorted_data)
