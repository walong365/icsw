#!/usr/bin/python-init -Otu

from django.core.exceptions import ValidationError, ImproperlyConfigured

# helper functions
def _check_integer(inst, attr_name, **kwargs):
    cur_val = getattr(inst, attr_name)
    min_val, max_val = (kwargs.get("min_val", None),
                        kwargs.get("max_val", None))
    if cur_val is None and kwargs.get("none_to_zero", False):
        cur_val = 0
    try:
        cur_val = int(cur_val)
    except:
        raise ValidationError("%s is not an integer" % (attr_name))
    else:
        if min_val is not None and max_val is not None:
            if min_val is None:
                if cur_val > max_val:
                    raise ValidationError("%s too high (%d > %d)" % (
                        attr_name,
                        cur_val,
                        max_val))
            elif max_val is None:
                if cur_val < min_val:
                    raise ValidationError("%s too low (%d < %d)" % (
                        attr_name,
                        cur_val,
                        min_val))
            else:
                if cur_val < min_val or cur_val > max_val:
                    raise ValidationError("%s (%d) not in [%d, %d]" % (
                        attr_name,
                        cur_val,
                        min_val,
                        max_val))
        setattr(inst, attr_name, cur_val)
        return cur_val

def _check_float(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    try:
        cur_val = float(cur_val)
    except:
        raise ValidationError("%s is not a float" % (attr_name))
    setattr(inst, attr_name, cur_val)

def _check_empty_string(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    if not cur_val.strip():
        raise ValidationError("%s can not be empty" % (attr_name))

def _check_non_empty_string(inst, attr_name):
    cur_val = getattr(inst, attr_name)
    if cur_val.strip():
        raise ValidationError("%s must be empty" % (attr_name))


