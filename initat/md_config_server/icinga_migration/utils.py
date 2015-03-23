# -*- coding: utf-8 -*-
from functools import wraps

from django.db import models


PYNAG_OBJECT_ATTRIBUTE = "_PYNAG_OBJECT"
NOCTUA_OBJECT_ATTRIBUTE = "_NOCTUA_OBJECT"


def flags_to_dict(flags, defaultflags, mapping):
    """ Create a True/False mapping from icinga style flag lists.

    If flags is empty the resulting mapping is created from defaultflags.

    mapping should be a dict mapping flags to dictionary keys. The flag "n"
    has the special meaning "No options" - it must be part of the mapping
    to be enabled.
    """
    result = {}

    def strip_split(inputstring, seperator=","):
        inputstring = inputstring.strip()
        return [i.strip() for i in inputstring.split(seperator)]

    def bulkset(value):
        for key, name in mapping.items():
            if key == "n":
                continue
            result[name] = value

    if not flags:
        flags = defaultflags

    flags = strip_split(flags)
    if "n" in mapping and "n" in flags:
        bulkset(False)
    else:
        for key, name in mapping.items():
            if key == "n":
                continue
            result[name] = key in flags

    return result


def to_bool(x):
    """ Transform icinga "integer booleans" to bool objects. """
    return x in (1, "1")


def memoize_by_attribute(attribute, cache):
    """ Memoize based on the given attribute.

    The attribute value is taken from the first argument.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            obj = args[0]
            key = getattr(obj, attribute)
            if key not in cache:
                cache[key] = func(*args, **kwargs)
            else:
                print "Cached value: {}={}".format(
                    obj.__class__.__name__, key
                )
            return cache[key]
        return wrapper
    return decorator


def connect_objects(noctua_obj, pynag_obj):
    """ Connect a Noctua instance to a pynag instance.

    This creates a cycle between the two objects!
    """
    setattr(noctua_obj, PYNAG_OBJECT_ATTRIBUTE, pynag_obj)
    setattr(pynag_obj, NOCTUA_OBJECT_ATTRIBUTE, noctua_obj)


def get_connected_object(obj):
    """ Return the connected object. """
    if isinstance(obj, models.Model):
        return getattr(obj, PYNAG_OBJECT_ATTRIBUTE)
    else:
        return getattr(obj, NOCTUA_OBJECT_ATTRIBUTE)
