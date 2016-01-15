#!/bin/sh -ex

/opt/cluster/sbin/icsw setup --engine psql --user cdbuser --database cdbase --host localhost --passwd init4u --port 5432
