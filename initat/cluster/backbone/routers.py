#!/usr/bin/python-init -Otu


class db_router(object):
    def db_for_read(self, model, **hints):
        return None

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj_1, obj_2, **hints):
        return True

    def allow_syncdb(self, db, model, **hints):
        return True
