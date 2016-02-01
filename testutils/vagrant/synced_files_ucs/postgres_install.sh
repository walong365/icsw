#!/bin/bash -ex
# FIXIT ON TEMPLATE
echo "###########"
echo "Install postgresql server and psycopg2 packages"

apt-get update
apt-get install postgresql-9.1 python-psycopg2 --assume-yes

echo "###########"
echo "Initialize postgres db"

#postgresql-setup initdb

echo "###########"
echo "remove generated pg_hba.conf"
rm -rf /etc/postgresql/9.1/main/pg_hba.conf

echo "###########"
echo "write pg_hba file and set permissions and owner"
echo "#Allow any IP to connect, with a password:
host    all         all         0.0.0.0          0.0.0.0      trust
host    all         all         ::1/128                       trust
local   all         all                                       trust" > /etc/postgresql/9.1/main/pg_hba.conf

chown postgres:postgres /etc/postgresql/9.1/main/pg_hba.conf
chmod 600 /etc/postgresql/9.1/main/pg_hba.conf

echo "###########"
echo "restart postgresql server"
service postgresql restart

echo "###########"
echo "create database, user and set password"
sudo -u postgres psql --command "CREATE USER cdbuser LOGIN NOCREATEDB UNENCRYPTED PASSWORD '123abc';"
sudo -u postgres psql --command "CREATE DATABASE cdbase OWNER cdbuser;"
exit 0