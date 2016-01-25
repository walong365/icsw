#!/bin/bash -ex
psql cdbuser -d cdbase -c "UPDATE device_variable SET val_str = 'DSBP36-FB18' WHERE name = 'CLUSTER_ID';"
