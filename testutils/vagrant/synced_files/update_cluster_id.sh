#!/bin/bash -ex
psql UPDATE device_variable SET val_str = 'my_cluster_id' WHERE name = 'CLUSTER_ID';
