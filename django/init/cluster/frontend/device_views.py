# device views

import json
import pprint
import logging_tools
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from init.cluster.backbone.models import device_type, device_group, device
from lxml import etree
from lxml.builder import E

@login_required
@init_logging
def device_tree(request):
    return render_me(request ,"device_tree.html")()

@login_required
@init_logging
def get_json_tree(request):
    _post = request.POST
    pprint.pprint(_post)
    full_tree = device_group.objects.all().prefetch_related("device", "device_group").distinct().order_by("name")
    json_struct = []
    for cur_dg in full_tree:
        cur_devs = []
        for sub_dev in cur_dg.device_group.all():
            cur_devs.append({"title" : unicode(sub_dev)})
        cur_jr = {"title" : unicode(cur_dg),
                  "isFolder" : "1",
                  "children" : cur_devs}
        json_struct.append(cur_jr)
    return HttpResponse(json.dumps(json_struct),
                        mimetype="application/json")


@init_logging
def get_xml_tree(request):
    _post = request.POST
    full_tree = device_group.objects.all().prefetch_related("device", "device_group").distinct().order_by("name")
    xml_resp = E.response()
    for cur_dg in full_tree:
        dev_list = E.devices()
        for cur_d in cur_dg.device_group.all():
            d_el = E.device(
                unicode(cur_d),
                name=cur_d.name,
                comment=cur_d.comment,
                device_type="%d" % (cur_d.device_type_id),
                device_group="%d" % (cur_d.device_group_id),
                idx="%d" % (cur_d.pk)
            )
            dev_list.append(d_el)
        dg_el = E.device_group(
            dev_list,
            unicode(cur_dg),
            name=cur_dg.name,
            description=cur_dg.description,
            idx="%d" % (cur_dg.pk), is_cdg="1" if cur_dg.cluster_device_group else "0")
        xml_resp.append(dg_el)
    # add device type
    xml_resp.append(
        E.device_types(
            *[E.device_type(name=cur_dt.description, identifier=cur_dt.identifier, idx="%d" % (cur_dt.pk))
              for cur_dt in device_type.objects.all()]
        )
    )
    request.xml_response["response"] = xml_resp
    #request.log("catastrophic error", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@init_logging
def change_xml_entry(request):
    _post = request.POST
    try:
        object_type, attr_name, object_id = _post["id"].split("__", 2)
    except:
        request.log("cannot parse", logging_tools.LOG_LEVEL_ERROR, xml=True)
    else:
        if object_type == "dg":
            mod_obj = device_group
        elif object_type == "d":
            mod_obj = device
        else:
            request.log("unknown object_type '%s'" % (object_type), logging_tools.LOG_LEVEL_ERROR, xml=True)
            mod_obj = None
        if mod_obj:
            try:
                cur_obj = mod_obj.objects.get(pk=object_id)
            except mod_obj.DoesNotExist:
                request.log("object %s with id %s does not exit" % (object_type,
                                                                    object_id), logging_tools.LOG_LEVEL_ERROR, xml=True)
            else:
                new_value = _post["value"]
                old_value = getattr(cur_obj, attr_name)
                if attr_name == "device_type":
                    new_value = device_type.objects.get(pk=new_value)
                setattr(cur_obj, attr_name, new_value)
                try:
                    cur_obj.save()
                except:
                    request.xml_response["original_value"] = old_value
                    request.log("cannot change from %s to %s" % (unicode(old_value), unicode(new_value)),
                                logging_tools.LOG_LEVEL_ERROR,
                                xml=True)
                else:
                    request.log("changed %s from %s to %s" % (attr_name, unicode(old_value), unicode(new_value)), xml=True)
    return request.xml_response.create_response()
