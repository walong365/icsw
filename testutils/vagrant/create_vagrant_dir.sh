#!/bin/bash -ex

#
# This script creates a vagrant dir for a distribution containing
# - Vagrantfile
# - synced_files: merge of original synced_files as well as synced_files for the specific distro
#
# Also, git does not support symlinks, so we have to copy files which
# are only once in git anyway.
#

if [ $# -ne 1 ] ; then
    echo "USAGE: $0 LINUX_DISTRIBUTION"
    exit 1
fi

VAGRANT_TEST_UTILS_SOURCE="testutils/vagrant"
VAGRANT_DIR="../../install_test_vagant"
SYNC_DIR="synced_files"

mkdir -p $VAGRANT_DIR/$SYNC_DIR

cp $VAGRANT_TEST_UTILS_SOURCE/synced_files/* "$VAGRANT_DIR/synced_files"

if [ "$1" = "centos" ] ; then
    cp "$VAGRANT_TEST_UTILS_SOURCE/Vagrantfile.centos" "$VAGRANT_DIR/Vagrantfile"
    cp $VAGRANT_TEST_UTILS_SOURCE/synced_files_centos/* "$VAGRANT_DIR/synced_files"
else
    echo "Invalid linux distribution: $1"
    exit 1
fi
