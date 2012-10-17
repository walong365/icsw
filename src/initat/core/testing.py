import re
from lxml import etree

LXML_NS = re.compile(r'{.*}')


def xml_equal(x1, x2, compare_text=False, compare_tail=False, ignore_ns=False):
    """ Test if to xml trees are equal. """
    if ignore_ns:
        if not re.sub(LXML_NS, x1.tag, "") == re.sub(LXML_NS, x2.tag, ""):
            return False
    else:
        if not x1.tag == x2.tag:
            return False

    if compare_text:
        if not x1.text == x2.text:
            return False

    if compare_tail:
        if not x1.tail == x2.tail:
            return False

    x1a = dict(x1.attrib)
    x2a = dict(x2.attrib)

    if not x1a == x2a:
        return False

    x1c = x1.getchildren()
    x2c = x2.getchildren()

    if not len(x1c) == len(x2c):
        return False

    for c1, c2 in zip(x1c, x2c):
        if not xml_equal(c1, c2, compare_text=compare_text, compare_tail=compare_tail, ignore_ns=ignore_ns):
            return False

    return True
