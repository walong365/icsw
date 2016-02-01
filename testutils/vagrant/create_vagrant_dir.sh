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
VAGRANT_DIR="install_test_vagrant"
SYNC_DIR="synced_files"

if [ -d $VAGRANT_DIR ]; then
    echo "remove existing vagrant dir $VAGRANT_DIR"
    rm -r $VAGRANT_DIR
fi

mkdir -p $VAGRANT_DIR/$SYNC_DIR
cp "$VAGRANT_TEST_UTILS_SOURCE/vagrant_insecure_key" "$VAGRANT_DIR/vagrant_insecure_key"
cp "tools/install_icsw.py" "$VAGRANT_DIR/$SYNC_DIR"
cp $VAGRANT_TEST_UTILS_SOURCE/synced_files/* "$VAGRANT_DIR/$SYNC_DIR"

if [ "$1" = "centos" ] ; then
    cp "$VAGRANT_TEST_UTILS_SOURCE/Vagrantfile.centos" "$VAGRANT_DIR/Vagrantfile"
    cp $VAGRANT_TEST_UTILS_SOURCE/synced_files_centos/* "$VAGRANT_DIR/$SYNC_DIR"

elif [ "$1" = "debian" ] ; then
    cp "$VAGRANT_TEST_UTILS_SOURCE/Vagrantfile.debian" "$VAGRANT_DIR/Vagrantfile"
    cp $VAGRANT_TEST_UTILS_SOURCE/synced_files_debian/* "$VAGRANT_DIR/$SYNC_DIR"

elif [ "$1" = "univention" ] ; then
    cp "$VAGRANT_TEST_UTILS_SOURCE/Vagrantfile.ucs" "$VAGRANT_DIR/Vagrantfile"
    cp $VAGRANT_TEST_UTILS_SOURCE/synced_files_ucs/* "$VAGRANT_DIR/$SYNC_DIR"

elif [ "$1" = "ucs_32" ] ; then
    cp "$VAGRANT_TEST_UTILS_SOURCE/Vagrantfile.ucs_32" "$VAGRANT_DIR/Vagrantfile"
    cp $VAGRANT_TEST_UTILS_SOURCE/synced_files_ucs_32/* "$VAGRANT_DIR/$SYNC_DIR"

elif [ "$1" = "suse" ] ; then
    cp "$VAGRANT_TEST_UTILS_SOURCE/Vagrantfile.suse" "$VAGRANT_DIR/Vagrantfile"
    cp $VAGRANT_TEST_UTILS_SOURCE/synced_files_suse/* "$VAGRANT_DIR/$SYNC_DIR"
else
    echo "Invalid linux distribution: $1"
    exit 1
fi
