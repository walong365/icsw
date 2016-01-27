#!/bin/bash -ex
#
echo "###########"
echo "Refresh repo and Install postgresql server and psycopg2 packages"
zypper ref
zypper --no-gpg-checks --non-interactive install postgresql-server python-modules-psycopg2
systemctl enable postgresql
systemctl restart postgresql

echo "###########"
echo "remove generated pg_hba.conf"
rm -rf /var/lib/pgsql/data/pg_hba.conf

echo "###########"
echo "write pg_hba file and set permissions and owner"
echo "#Allow any IP to connect, with a password:
host    all         all         0.0.0.0          0.0.0.0      trust
host    all         all         ::1/128                       trust
local   all         all                                       trust" > /var/lib/pgsql/data/pg_hba.conf
chown postgres:postgres /var/lib/pgsql/data/pg_hba.conf
chmod 600 /var/lib/pgsql/data/pg_hba.conf

echo "###########"
echo "restart postgresql server"
systemctl restart postgresql

echo "###########"
echo "create database, user and set password"
sudo -u postgres psql --command "CREATE USER cdbuser LOGIN NOCREATEDB UNENCRYPTED PASSWORD '123abc';"
sudo -u postgres psql --command "CREATE DATABASE cdbase OWNER cdbuser;"
exit 0
