# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# This file is part of cluster-backbone-sql
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
""" Complementary wrapper around django reversion """

import django

from reversion import revisions as reversion

from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db import models
from django.db.models.signals import post_delete
from django.utils.encoding import force_text

from initat.cluster.backbone.middleware import thread_local_middleware
from initat.cluster.backbone.models import user


class icsw_deletion_record(models.Model):
    """Record deletions of objects since this is missing in reversion.
    Model is similar to reversion.models.Version"""

    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey("backbone.user", blank=True, null=True, on_delete=models.SET_NULL)

    object_id_int = models.IntegerField()  # only integer keys supported atm
    content_type = models.ForeignKey(ContentType)

    serialized_data = models.TextField()
    object_repr = models.TextField()

    @classmethod
    def register(cls, model):
        post_delete.connect(cls._on_post_delete, model)

    @staticmethod
    def _on_post_delete(sender, instance, **kwargs):
        serialized_data = serializers.serialize('json', (instance,))
        content_type = ContentType.objects.get_for_model(sender)
        acting_user = thread_local_middleware().user

        if not isinstance(acting_user, user):
            acting_user = None

        try:
            # use smart way
            object_repr = force_text(instance)
        except:
            try:
                # smart way might use something which has already been deleted, try it more direct
                object_repr = repr(instance)
            except:
                object_repr = "object"

        record = icsw_deletion_record(
            user=acting_user,
            object_id_int=instance.pk,
            content_type=content_type,
            serialized_data=serialized_data,
            object_repr=object_repr
        )
        record.save()


def icsw_register(model):
    """Registers model with reversion plus additional deletion log.
    Also makes sure that a revision is created if save() is called manually outside of a revision contact
    """
    reversion.register(model)
    icsw_deletion_record.register(model)

    icsw_register.REGISTERED_MODELS.append(model)

    def create_save_with_reversion(original_save):
        def save_with_reversion(*args, **kwargs):
            if not reversion.revision_context_manager.is_active():
                with reversion.create_revision():
                    original_save(*args, **kwargs)
            else:
                original_save(*args, **kwargs)
        return save_with_reversion

    model.save = create_save_with_reversion(model.save)

    # TODO: bulk_save/delete?
    # TODO: user is currently set to NULL in both reversion and here on deletion


icsw_register.REGISTERED_MODELS = []
