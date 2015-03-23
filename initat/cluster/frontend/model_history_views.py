# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
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
# -*- coding: utf-8 -*-
#
import json
import user
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import ForeignKey
import itertools
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from rest_framework.response import Response
import reversion
import initat
from initat.cluster.backbone.models.model_history import icsw_deletion_record, icsw_register
from rest_framework.generics import ListAPIView, RetrieveAPIView
from initat.cluster.frontend.rest_views import rest_logging
from initat.cluster.backbone.render import render_me


class history_overview(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        return render_me(request, "history_overview.html")()


class get_models_with_history(RetrieveAPIView):
    @method_decorator(login_required)
    @rest_logging
    def get(self, request, *args, **kwargs):
        return Response({model.__name__: model._meta.verbose_name for model in icsw_register.REGISTERED_MODELS})


class get_historical_data(ListAPIView):
    @method_decorator(login_required)
    @rest_logging
    def list(self, request, *args, **kwargs):
        model_name = request.GET['model']
        model = getattr(initat.cluster.backbone.models, model_name)

        def format_version(version):
            serialized_data = json.loads(version.serialized_data)[0]
            return_data = serialized_data['fields']
            return_data['pk'] = serialized_data['pk']

            if version.revision.comment == "Initial version.":
                type = "initial"
            else:
                type = None

            meta = {
                'date': version.revision.date_created,
                'user': version.revision.user_id,
                'type': type,
                'object_repr': version.object_repr
            }
            return {'meta': meta, 'data': return_data}

        def format_deletion(deletion):
            meta = {
                'date': deletion.date,
                'user': deletion.user_id,
                'type': 'deleted',
                'object_repr': deletion.object_repr
            }

            serialized_data = json.loads(deletion.serialized_data)[0]
            return_data = serialized_data['fields']
            return_data['pk'] = serialized_data['pk']

            return {'meta': meta, 'data': return_data}

        content_type = ContentType.objects.get_for_model(model)
        deletion_queryset = icsw_deletion_record.objects.filter(content_type=content_type)
        version_queryset = reversion.models.Version.objects.filter(content_type=content_type).select_related('revision')

        sorted_data = sorted(
            itertools.chain(
                (format_version(ver) for ver in version_queryset),
                (format_deletion(dele) for dele in deletion_queryset)
            ),
            key=lambda elem: elem['meta']['date']
        )

        foreign_keys = [foreign_key for foreign_key in model._meta.concrete_model._meta.local_fields
                        if isinstance(foreign_key, ForeignKey)]

        m2ms = [m2m for m2m in model._meta.concrete_model._meta.local_many_to_many
                if m2m.rel.through._meta.auto_created]
        # only serialized m2ms, which are by djangos logic the ones which are not autocreated

        def resolve_reference(target_model, foreign_key_val):
            try:
                return unicode(target_model.objects.get(pk=foreign_key_val))
            except target_model.DoesNotExist:
                deleted_queryset = reversion.get_deleted(target_model)
                # unicode on Version object gives the saved object repr, which we use here
                return unicode(deleted_queryset.get(object_id=foreign_key_val))

        # TODO: only transmit changes (save last state per pk during iteration)
        # set missing type info
        pk_seen = set()
        for entry in sorted_data:
            if not entry['meta']['type']:
                if entry['data']['pk'] in pk_seen:
                    entry['meta']['type'] = 'modified'
                else:
                    entry['meta']['type'] = 'created'

            pk_seen.add(entry['data']['pk'])

            # resolve keys to current value or last known one
            for foreign_key in foreign_keys:
                # field might not have existed at the time of saving, so check (and don't resolve null values)
                if foreign_key.name in entry['data'] and entry['data'][foreign_key.name] is not None:
                    entry['data'][foreign_key.name] =\
                        resolve_reference(foreign_key.rel.to, entry['data'][foreign_key.name])

            for m2m in m2ms:
                # field might not have existed at the time of saving, so check
                if m2m.name in entry['data']:
                    entry['data'][m2m.name] =\
                        list(resolve_reference(m2m.rel.to, m2m_val) for m2m_val in entry['data'][m2m.name])

        return Response(sorted_data)


