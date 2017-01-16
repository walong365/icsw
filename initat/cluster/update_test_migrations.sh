#!/bin/bash

mv ./backbone/migrations ./backbone/old_migrations

mv ./backbone/test_migrations/ ./backbone/migrations

rm ./backbone/migrations/0001_initial.py*

./manage.py makemigrations backbone

mv ./backbone/migrations ./backbone/test_migrations

mv ./backbone/old_migrations ./backbone/migrations
