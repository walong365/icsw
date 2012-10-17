"""
The initat.core testsuite
"""
import unittest
from lxml import etree

from initat.core.testing import xml_equal


class xml_equal_test(unittest.TestCase):
    def setUp(self):
        XML = """
        <a a="a" b="b">
            <b />
            <c>
                <a c="c">TEXT</a>
            </c>TAIL
        </a>
        """
        XML_SAME_SOFT = """
        <a a="a" b="b"><b /><c><a c="c">OTHERTEXT</a></c>OTHERTAIL</a>
        """

        XML_ATTR = """
        <a a="a" b="b">
            <b />
            <c>
                <!--DIFFERENCE-->
                <a c="d">TEXT</a>
            </c>TAIL
        </a>
        """
        # Differs only in namespace and xmlns tag
        XML_NS = """
        <a:a a="a" b="b" xmlns:a="http://example.com/example-xml/">
            <a:b />
            <a:c>
                <a:a c="c">TEXT</a:a>
            </a:c>TAIL
        </a:a>
        """
        XML_TAG = """
        <a a="a" b="b">
            <!--DIFFERENCE-->
            <d />
            <c>
                <a c="c">TEXT</a>
            </c>TAIL
        </a>
        """

        XML_TEXT = """
        <a a="a" b="b">
            <b />
            <c>TEXT
                <a c="c">TEXT</a>
            </c>TAIL
        </a>
        """

        XML_TAIL = """
        <a a="a" b="b">
            <b />
            <c>
                <a c="c">TEXT</a>
            </c>OTHERTAIL
        </a>
        """
        self.xml = etree.fromstring(XML)
        self.xml_same = etree.fromstring(XML_SAME_SOFT)
        self.xml_attr = etree.fromstring(XML_ATTR)
        self.xml_ns = etree.fromstring(XML_NS)
        self.xml_tag = etree.fromstring(XML_TAG)
        self.xml_text = etree.fromstring(XML_TEXT)
        self.xml_tail = etree.fromstring(XML_TAIL)

    def test_identity(self):
        self.assertTrue(xml_equal(self.xml, self.xml))

        self.assertTrue(xml_equal(self.xml, self.xml_same))
        # Sanity check
        self.assertTrue(xml_equal(self.xml_same, self.xml))

    def test_identity_strict(self):
        self.assertTrue(xml_equal(self.xml, self.xml, compare_text=True, compare_tail=True))

        self.assertFalse(xml_equal(self.xml, self.xml_same, compare_text=True, compare_tail=True))
        # Sanity check
        self.assertFalse(xml_equal(self.xml_same, self.xml, compare_text=True, compare_tail=True))

    def test_attr_difference(self):
        self.assertTrue(xml_equal(self.xml_attr, self.xml_attr))
        self.assertFalse(xml_equal(self.xml, self.xml_attr))
        self.assertFalse(xml_equal(self.xml, self.xml_attr, compare_text=True, compare_tail=True))

    def test_ns_difference(self):
        self.assertTrue(xml_equal(self.xml_ns, self.xml_ns))
        # ignore namespaces
        self.assertTrue(xml_equal(self.xml, self.xml_ns, ignore_ns=True))
        self.assertTrue(xml_equal(self.xml, self.xml_ns, compare_text=True, compare_tail=True, ignore_ns=True))
        # don't ignore namespaces
        self.assertFalse(xml_equal(self.xml, self.xml_ns))
        self.assertFalse(xml_equal(self.xml, self.xml_ns, compare_text=True, compare_tail=True))

    def test_tag_difference(self):
        self.assertTrue(xml_equal(self.xml_tag, self.xml_tag))
        self.assertFalse(xml_equal(self.xml, self.xml_tag))
        self.assertFalse(xml_equal(self.xml, self.xml_tag, compare_text=True, compare_tail=True))

    def test_text_difference(self):
        self.assertTrue(xml_equal(self.xml, self.xml_text))
        self.assertTrue(xml_equal(self.xml, self.xml_text, compare_tail=True))

        self.assertFalse(xml_equal(self.xml, self.xml_text, compare_text=True))
        self.assertFalse(xml_equal(self.xml, self.xml_text, compare_text=True, compare_tail=True))

    def test_tail_difference(self):
        self.assertTrue(xml_equal(self.xml, self.xml_tail))
        self.assertTrue(xml_equal(self.xml, self.xml_tail, compare_text=True))
        self.assertFalse(xml_equal(self.xml, self.xml_tail, compare_tail=True))
        self.assertFalse(xml_equal(self.xml, self.xml_tail, compare_tail=True, compare_text=True))
