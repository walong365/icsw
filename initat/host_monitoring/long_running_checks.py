# -*- coding: utf-8 -*-

from multiprocessing import Process

LONG_RUNNING_CHECK_RESULT_KEY = "long_running_check_result"


class LongRunningCheck(object):
    """ Represents a long running check.

    Objects of this class are usually returned in __call__ of a hm_command.
    Doing this signals the server that code should be executed "in the
    background".
    """
    def perform_check(self, queue):
        """ Override this method with the implementation of the actual check.
        """
        raise NotImplementedError()

    def start(self, queue):
        p = Process(target=self.perform_check, args=(queue, ))
        p.start()
        return p
