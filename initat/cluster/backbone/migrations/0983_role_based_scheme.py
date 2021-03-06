# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-25 08:45


from django.db import migrations, models
from django.db.models import Q


def dummy_reverse(apps, schema_editor):
    Role = apps.get_model("backbone", "role")
    Role.objects.all().delete()


def migrate_to_role_based_auth_model(apps, schema_editor):
    Role = apps.get_model("backbone", "role")
    user = apps.get_model("backbone", "user")
    group = apps.get_model("backbone", "group")
    csw_perm = apps.get_model("backbone", "csw_permission")
    csw_obj_perm = apps.get_model("backbone", "csw_object_permission")
    content_type = apps.get_model("contenttypes", "contenttype")

    g_perm, o_perm = (
        apps.get_model("backbone", "RolePermission"),
        apps.get_model("backbone", "RoleObjectPermission"),
    )
    _ac_dict = {
        "user": (
            apps.get_model("backbone", "user_permission"),
            apps.get_model("backbone", "user_object_permission"),
        ),
        "group": (
            apps.get_model("backbone", "group_permission"),
            apps.get_model("backbone", "group_object_permission"),
        ),
    }
    # add perm for allowed_device_groups
    try:
        adg = csw_perm.objects.get(Q(codename="access_device_group"))
    except csw_perm.DoesNotExist:
        # fake creation
        adg = csw_perm.objects.create(
            codename="access_device_group",
            name="Allow access to device group",
            valid_for_object_level=True,
            content_type=content_type.objects.get(Q(model="device_group")),
        )
    for _src, _type in [(user, "user"), (group, "group")]:
        for entry in _src.objects.all():
            if _type == "user":
                _id_str = entry.login
            else:
                _id_str = entry.groupname
            if entry.allowed_device_groups.all().count():
                # new roles for allowed device groups
                adg_role = Role.objects.create(
                    name="{}Role_GroupAccess_{}".format(
                        _type,
                        _id_str,
                    )
                )
                entry.roles.add(adg_role)
                for group in entry.allowed_device_groups.all():
                    obj_right = csw_obj_perm.objects.create(
                        csw_permission=adg,
                        object_pk=group.idx,
                    )
                    o_perm.objects.create(
                        role=adg_role,
                        csw_object_permission=obj_right,
                        level=0,
                    )
            new_role = None
            for _obj_type, _model in zip(["global", "object"], _ac_dict[_type]):
                if _model.objects.filter(Q(**{_type: entry})).count():
                    if new_role is None:
                        # create new role
                        new_role = Role.objects.create(
                            name="{}Role_{}".format(_type, _id_str),
                            description="auto created",
                        )
                        entry.roles.add(new_role)
                        # entry.save(update_fields=["roles"])
                    # add objects
                    for _right in _model.objects.filter(Q(**{_type: entry})):
                        if _obj_type == "global":
                            new_g = g_perm.objects.create(
                                role=new_role,
                                csw_permission=_right.csw_permission,
                                level=_right.level,
                            )
                        else:
                            new_o = o_perm.objects.create(
                                role=new_role,
                                csw_object_permission=_right.csw_object_permission,
                                level=_right.level,
                            )
                    # print _obj_type, _model, _model.objects.filter(Q(**{_type: entry})).count()


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0982_role_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='description',
            field=models.TextField(blank=True, default=b''),
        ),
        migrations.RunPython(migrate_to_role_based_auth_model, reverse_code=dummy_reverse),
    ]
