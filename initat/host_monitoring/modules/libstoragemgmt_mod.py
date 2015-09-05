# -*- coding: utf-8 -*-

from .. import limits
from ..hm_classes import hm_command, hm_module
from ..long_running_checks import LongRunningCheck, LONG_RUNNING_CHECK_RESULT_KEY

try:
    import lsm
except ImportError:
    lsm = None


class _general(hm_module):
    def init_module(self):
        self.enabled = True
        if lsm:
            pass
        else:
            self.log("disabled libstoragemanagement because no lsm module found")
            self.enabled = False


class LibstoragemgmtCheck(LongRunningCheck):
    """ Query storage systems for information using libstoragemgmt. """
    def __init__(self, uri, password):
        self.uri = uri
        self.password = password

    def perform_check(self, queue):
        client = lsm.Client(self.uri, plain_text_password=self.password)

        result = {}
        mapping = (
            ("systems", client.systems),
            ("pools", client.pools),
            ("disks", client.disks),
        )
        for key, function in mapping:
            result[key] = [(i.name, i.status) for i in function()]
        client.close()
        queue.put(result)


class libstoragemgmt_command(hm_command):
    """
    A generic libstoragemgmt check. Needs a URI specifying the device to check.
    This check needs a running lsmd from the libstoragemgmt-init package.
    """
    def __init__(self, name):
        super(libstoragemgmt_command, self).__init__(
            name, positional_arguments=True
        )
        self.parser.add_argument(
            "uri", help="The URI of the storage device to check"
        )
        self.parser.add_argument(
            "password", help="The password to authenticate with"
        )

    def __call__(self, srv_command_obj, arguments):
        return LibstoragemgmtCheck(arguments.uri, arguments.password)

    def interpret(self, srv_com, *args, **kwargs):
        result = srv_com[LONG_RUNNING_CHECK_RESULT_KEY]
        result_strings = []
        mapping = (
            ("systems", lsm.System.STATUS_OK),
            ("pools", lsm.Pool.STATUS_OK),
            ("disks", lsm.Disk.STATUS_OK),
        )
        result_status = limits.nag_STATE_OK
        for key, status_ok in mapping:
            good = bad = 0
            for _, status in result[key]:
                if status & status_ok:
                    good += 1
                else:
                    result_status = limits.nag_STATE_CRITICAL
                    bad += 1
            result_strings.append("{}: (good={} bad={})".format(
                key, good, bad
            ))
        return result_status, ", ".join(result_strings)
