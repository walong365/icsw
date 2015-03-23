# -*- coding: utf-8 -*-

"""
TODO:
    * Make sure that the "admin" user is not set to inactive and is superuser.
      Even if no user exists. Report the password.

    * Perform unification and try to find equal templates. BM says, that
      mon_check_command and config have a 1-1 relationship - check with AL?

    * The arguments to commands are not converted to noctua objects. What
      should we use? backbone.config?

    * Is it necessary to clean up the connections done by connect_object?
    * Put the categories under /mon/
"""

import operator

import pyparsing
from pyparsing import Literal, Word, Combine, nums, Forward
from pynag.Model import (
    Service, Host, Hostgroup, Timeperiod, Command, Hostgroup, Contact
)

from initat.cluster.backbone.models import *

from .utils import (
    flags_to_dict, to_bool, memoize_by_attribute, connect_objects
)

DEFAULT_CONTACT_GROUP_NAME = "noctua-contact-group"
DEFAULT_DEVICE_GROUP_NAME = "noctua-device-group"
DEFAULT_TIME_RANGE = "00:00-24:00"
DEFAULT_TIMEPERIOD_NAME = "noctua_24x7"
SINGLE_USER_GROUP_SUFFIX = "-single-user"


CACHES = {
    "service": {},
    "command": {},
    "timeperiod": {},
    "host": {},
    "hostgroup": {},
    "contact": {},
    "contactgroup": {},
}


def get_default_timeperiod():
    defaults = {
        "sun_range": DEFAULT_TIME_RANGE,
        "mon_range": DEFAULT_TIME_RANGE,
        "tue_range": DEFAULT_TIME_RANGE,
        "wed_range": DEFAULT_TIME_RANGE,
        "thu_range": DEFAULT_TIME_RANGE,
        "fri_range": DEFAULT_TIME_RANGE,
        "sat_range": DEFAULT_TIME_RANGE,
    }
    result, _ = mon_period.objects.get_or_create(
        name=DEFAULT_TIMEPERIOD_NAME,
        defaults=defaults
    )
    return result


@memoize_by_attribute("timeperiod_name", CACHES["timeperiod"])
def transform_timeperiod(timeperiod):
    print "transform_timeperiod"
    """ Transform an icinga timeperiod into a mon_period object.

    Only simple weekday notation is supported.
    """
    days = (
        Literal("monday") | Literal("tuesday") | Literal("wednesday") |
        Literal("thursday") | Literal("friday") | Literal("saturday") |
        Literal("sunday")
    )
    hours = reduce(operator.or_, [Literal("{:02d}".format(i)) for i in range(25)])
    minutes = reduce(operator.or_, [Literal("{:02d}".format(i)) for i in range(61)])
    point_in_time = Combine(hours + ":" + minutes)
    date = Combine(point_in_time + "-" + point_in_time)
    multiple_dates = Forward()
    multiple_dates << Combine(Combine(date + "," + multiple_dates) | date)
    grammar = days.setResultsName("key") + multiple_dates.setResultsName("value")

    values = {}
    known_keys = {
        "id", "shortname", "alias", "timeperiod_name", "exclude",
        "meta", "effective_command_line",
    }
    for key in set(timeperiod.keys()) - known_keys:
        try:
            tokens = grammar.parseString(key)
        except pyparsing.ParseException:
            print "Timeperiod: Could not parse: {!r}".format(key)
        else:
            values[tokens.key] = tokens.value

    # their name: our name
    rename = {
        "sunday": "sun_range",
        "monday": "mon_range",
        "tuesday": "tue_range",
        "wednesday": "wed_range",
        "thursday": "thu_range",
        "friday": "fri_range",
        "saturday": "sat_range",
    }
    defaults = {}
    for their_name, our_name in rename.items():
        defaults[our_name] = values.get(their_name, DEFAULT_TIME_RANGE)

    result, _ = mon_period.objects.get_or_create(
        name=timeperiod["timeperiod_name"],
        alias=timeperiod["alias"],
        defaults=defaults,
    )
    return result


@memoize_by_attribute("hostgroup_name", CACHES["hostgroup"])
def transform_hostgroup(hostgroup):
    print "transform_hostgroup"
    result, _ = device_group.objects.get_or_create(
        name=hostgroup["hostgroup_name"],
        defaults={
            "description": hostgroup["alias"],
        }
    )
    return result


@memoize_by_attribute("host_name", CACHES["host"])
def transform_host(host):
    print "transform_host"
    """ Transform an icinga host into a device object.

    The first hostgroup to match valid_domain_re is used for device_group. The
    remaining hostgroups are mapped into "/mon/..." categories.
    """
    primary = None
    secondary = []
    for hostgroup in host.get_effective_hostgroups():
        name = hostgroup["hostgroup_name"]
        if primary is None and valid_domain_re.match(name):
            primary = transform_hostgroup(hostgroup)
        else:
            # FIXME: Does not work this way!
            # category_obj, _ = category.objects.get_or_create(name="/mon/"+name)
            # secondary.append(category_obj)
            pass
    if primary is None:
        primary, _ = device_group.objects.get_or_create(
            name=DEFAULT_DEVICE_GROUP_NAME,
        )

    print "Host={host.host_name}, primary={primary}, secondary={secondary}".format(
        **locals()
    )

    defaults = {
        "device_group": primary,
        "alias": host["alias"],
        "device_type": device_type.objects.get(identifier="H"),
    }

    result, device_created = device.objects.get_or_create(
        name=host["host_name"],
        defaults=defaults,
    )
    if host["address"]:
        default_network, _ = network.objects.get_or_create(
            network="0.0.0.0",
            defaults={
                "netmask": "0.0.0.0",
                "broadcast": "255.255.255.255",
                "gateway": "0.0.0.0",
                "identifier": "all",
                "network_type": network_type.objects.get(Q(identifier="o")),
            }
        )
        if device_created:
            netdevice_obj = netdevice.objects.create(
                device=result,
                devname="eth0",
            )
            net_ip.objects.create(
                netdevice=netdevice_obj,
                network=default_network,
                ip=host["address"],
            )

    # Associated the "host_check_command". This creates the *main* mon_device_templ
    # and mon_service_templ objects for the device.
    main_service_template, _ = mon_service_templ.objects.get_or_create(
        name=result.name + "-service-template",
        defaults={
            "nsc_period": get_default_timeperiod(),
            "nsn_period": get_default_timeperiod(),
        }
    )
    try:
        host_check_command = host.get_effective_check_command()
    except KeyError:
        # No host check defined
        print "No host check defined: {}".format(host)
        host_check_command = None
    else:
        host_check_command = transform_command_to_host_check_command(
            host_check_command
        )

    main_template, _ = mon_device_templ.objects.get_or_create(
        name=result.name + "-template",
        defaults={
            "mon_service_templ": main_service_template,
            "not_period": get_default_timeperiod(),
            "mon_period": get_default_timeperiod(),
            "host_check_command": host_check_command,
        }
    )
    if device_created:
        result.mon_device_templ = main_template
        result.save()

    result.categories.add(*secondary)

    for service in host.get_effective_services():
        monitoring_template = transform_service(service)

        print "*" * 20
        print service.get_effective_check_command()
        print service.get_effective_command_line()
        print service["check_command"]
        print "*" * 20

        check_command = transform_command(service.get_effective_check_command())
        check_command.mon_service_templ = monitoring_template
        check_command.save()

        # Associate the mon_check_command.config through a device_config with
        # the device.
        device_config.objects.create(
            device=result,
            config=check_command.config,
        )
    connect_objects(result, host)
    return result


def transform_command(command):
    """ Transform an icinga command into a mon_check_command. """

    print "transform_command"
    name = command["command_name"]
    # Create a config and a command
    config_obj = config.objects.create(name=name)
    result = mon_check_command.objects.create(
        name=name,
        command_line=command["command_line"],
        config=config_obj,
    )
    return result


def transform_command_to_host_check_command(command):
    """ Transform an icinga command into a host_check_command object.

    This is a special variant of transform_command. The resulting object
    will be a host_check_command.
    """
    result, _ = host_check_command.objects.get_or_create(
        name=command["command_name"],
        defaults={
            "command_line": command["command_line"],
        }
    )
    return result


@memoize_by_attribute("service_description", CACHES["service"])
def transform_service(service):
    """ Transform an icinga service into a mon_service_templ object.

    This transformation differs from the other transformations insofar as it
    does not create all related objects. The associated command is not created
    because in the CSW data model a command is connected to a device via a
    device config and not connected to a mon_service_template.
    """

    print "transform_service", service["service_description"]
    check_period = transform_timeperiod(
        Timeperiod.objects.filter(timeperiod_name=service["check_period"])[0]
    )
    notification_period = transform_timeperiod(
        Timeperiod.objects.filter(timeperiod_name=service["notification_period"])[0]
    )

    defaults = {
        "nsc_period": check_period,
        "nsn_period": notification_period,
    }

    notification_options = service["notification_options"]
    notification_mapping = {
        "r": "nrecovery",
        "c": "ncritical",
        "w": "nwarning",
        "u": "nunknown",
        "f": "nflapping",
        "s": "nplanned_downtime",
        "n": None,
    }
    defaults.update(
        flags_to_dict(notification_options, "r,c,w,u,f,s", notification_mapping)
    )

    flap_detection_options = service["flap_detection_options"]
    flap_detection_mapping = {
        "o": "flap_detect_ok",
        "w": "flap_detect_warn",
        "c": "flap_detect_critical",
        "u": "flap_detect_unknown",
    }
    defaults.update(
        flags_to_dict(flap_detection_options, "o,w,c,u", flap_detection_mapping)
    )
    # theirs: ours
    generic_mapping = {
        "is_volatile": ("volatile", lambda x: True if x in ("1", "2") else False),
        "max_check_attempts": "max_attempts",
        "check_interval": "check_interval",
        "retry_interval": "retry_interval",
        "notification_interval": "ninterval",

        # Freshness
        "freshness_threshold": ("freshness_threshold", lambda x: max(int(x), 10)),
        "check_freshness": ("check_freshness", to_bool),

        # Flapping
        "low_flap_threshold": "low_flap_threshold",
        "high_flap_threshold": "high_flap_threshold",
        "flap_detection_enabled": ("flap_detection_enabled", to_bool),
    }
    for their_name, our_name in generic_mapping.items():
        value = getattr(service, their_name)
        if value:
            if isinstance(our_name, tuple):
                our_name, converter = our_name
                defaults[our_name] = converter(value)
            else:
                defaults[our_name] = value

    result, _ = mon_service_templ.objects.get_or_create(
        name=service["service_description"],
        defaults=defaults,
    )

    for contactgroup in service.get_effective_contact_groups():
        contactgroup = transform_contactgroup(contactgroup)
        contactgroup.service_templates.add(result)

    for contact in service.get_effective_contacts():
        _, single_user_group = transform_contact(
            contact, user_specific_group=True
        )
        single_user_group.service_templates.add(result)

    return result


# Don't perform memoization here, because of the user_specific_group argument
def transform_contact(contact, user_specific_group=False):
    """ Transform an icinga contact into a mon_contact object.

    Part of the transformation is creating and associating a user and a group
    object. The users created by this transformation will not be allowed to
    login.

    If user_specific_group == True, we create a user-specific mon_contactgroup
    object for the mon_contact, because we cannot directly associate mon_contacts
    with mon_service_templ objects. Icinga supports association of contactgroups
    and contacts with services.
    """
    print "transform_contact"
    try:
        next_uid = user.objects.latest("uid").uid + 1
    except user.DoesNotExist:
        next_uid = 100

    try:
        next_gid = group.objects.latest("gid").gid + 1
    except group.DoesNotExist:
        next_gid = 100

    default_group, _ = group.objects.get_or_create(
        groupname=DEFAULT_CONTACT_GROUP_NAME,
        defaults={
            "gid": next_gid,
        }
    )

    print "Creating user: {contact.contact_name}".format(**locals())
    user_obj, _ = user.objects.get_or_create(
        login=contact["contact_name"],
        defaults={
            "uid": next_uid,
            "email": contact["email"],
            "password": "password",
            "active": False,
            "group": default_group,
        }
    )
    print "User={user_obj.login} email={user_obj.email}".format(
        **locals()
    )

    # FIXME: It seems as if host_notification_command and service_notification_command
    # cannot be mapped to our model.
    host_notification_period = Timeperiod.objects.filter(
        timeperiod_name=contact["host_notification_period"]
    )[0]
    service_notification_period = Timeperiod.objects.filter(
        timeperiod_name=contact["service_notification_period"]
    )[0]

    defaults = {
        "snperiod": transform_timeperiod(service_notification_period),
        "hnperiod": transform_timeperiod(host_notification_period),
        "mon_alias": contact["alias"],
    }

    if to_bool(contact["service_notifications_enabled"]):
        service_notification_options = contact["service_notification_options"]
    else:
        service_notification_options = "n"
    service_notification_mapping = {
        "w": "snwarning",
        "s": "splanned_downtime",
        "f": "sflapping",
        "r": "snrecovery",
        "c": "sncritical",
        "u": "snunknown",
        "n": None,
    }
    defaults.update(
        flags_to_dict(service_notification_options, "n", service_notification_mapping)
    )

    if to_bool(contact["host_notifications_enabled"]):
        host_notification_options = contact["host_notification_options"]
    else:
        host_notification_options = "n"
    host_notification_mapping = {
        "d": "hndown",
        "u": "hnunreachable",
        "f": "hflapping",
        "r": "hnrecovery",
        "s": "hplanned_downtime",
        "n": None,
    }
    defaults.update(
        flags_to_dict(host_notification_options, "n", host_notification_mapping)
    )

    result, _ = mon_contact.objects.get_or_create(
        user=user_obj,
        defaults=defaults
    )

    if user_specific_group:
        # We need a mon_contactgroup to associate a mon_contact with a
        # mon_service_template
        single_user_group, created = mon_contactgroup.objects.get_or_create(
            name=contact["contact_name"] + SINGLE_USER_GROUP_SUFFIX,
            defaults={
                "alias": contact["alias"],
            }
        )
        if created:
            single_user_group.members.add(result)
        return result, single_user_group
    else:
        return result


@memoize_by_attribute("contactgroup_name", CACHES["contactgroup"])
def transform_contactgroup(contactgroup):
    """ Transform an icinga contactgroup into a mon_contactgroup object.

    All members of the contactgroup will be created as well.
    """
    print "transform_contactgroup"
    result, _ = mon_contactgroup.objects.get_or_create(
        name=contactgroup["contactgroup_name"],
        defaults={
            "alias": contactgroup["alias"],
        }
    )
    contacts = []
    for contact in contactgroup.get_effective_contacts():
        contact = transform_contact(contact)
        contacts.append(contact)
    result.members.add(*contacts)
    return result
