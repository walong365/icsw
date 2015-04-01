#!/bin/bash
set -e

PACKAGE_BASE="/usr/local/home/sieghart/dev/init-packages"
MERGED="git@repository:/srv/git/icsw.git"
LOG=/tmp/package-knife.log


PACKAGES=(cbc-tools cluster-backbone cluster-backbone-sql-migration \
    cluster-config-server cluster-server collectd-init discovery-server host-monitoring \
    initcore init-license-tools init-snmp-libs loadmodules logcheck-server logging-server \
    meta-server md-config-server mother package-install python-modules-base rms-tools \
    rms-tools-base rrd-grapher webfrontend)

function fix_setup() {
    echo "Renaming setup.py"
    packages=(cbc-tools host-monitoring initcore meta-server python-modules-base)
    for package in ${packages[@]}; do
        (cd $PACKAGE_BASE/$package
        sed -i "s#./setup.py#./${package}_setup.py#g" Makefile */Makefile
        sed -i "s# setup.py# ${package}_setup.py#g" Makefile */Makefile
        )
    done
}

function buildall() {
    echo "Building all packages"
    for package in ${PACKAGES[@]}; do
        (cd $PACKAGE_BASE/$package
        # Main package
        echo -n "Building $package ... "
        if stat -t *.tgz >/dev/null 2>&1; then
           echo "Skipped"
        else
            package-knife --increase-release-on-build true build --latest $package > $LOG 2>&1
            echo "OK"
        fi
        if stat -t */META >/dev/null 2>&1; then
            subpackages=$(ls */META -1 | sed 's./META..')
            for subpackage in $subpackages; do
                echo -n "Building $package/$subpackage ... "
                if stat -t $subpackage/*.tgz >/dev/null 2>&1; then
                   echo "Skipped"
                else
                    package-knife --increase-release-on-build true build --latest $package/$subpackage > $LOG 2>&1
                    echo "OK"
                fi
            done
        fi
        )
    done
}

function replace_source() {
    echo "Replacing source"
    for package in ${PACKAGES[@]}; do
        (cd $PACKAGE_BASE/$package
        metas=$(find . -name META)
        for meta in $metas; do
            sed -i "s#<p:source>.*</p:source>#<p:source>$MERGED</p:source>#" $meta
        done
        )
    done
}

function delete_meta_sources() {
    echo "Deleting stale meta-source directories"
    set +e
    find $PACKAGE_BASE -type d -iname "meta-source" -exec rm -rf {} \;
    find $PACKAGE_BASE -type d -iname "meta-source-latest" -exec rm -rf {} \;
    find $PACKAGE_BASE -type f -iname "meta-source-latest.tar.gz" -delete
    set -e
}

function remove_deprecated_packages() {
    to_remove=( \
        "rms-tools/1.x" "rms-tools-base/1.x rrd-grapher/1.x" "md-config-server/1.x" \ 
        "cluster-backbone-sql/1.x" \
    )
    cd $PACKAGE_BASE
    for i in ${to_remove[@]}; do
        if [[ -d $i ]]; then
            rm -rf $i
        fi
    done
}

remove_deprecated_packages
delete_meta_sources
#find $PACKAGE_BASE -type f -iname "*.tgz" -delete
replace_source
fix_setup
buildall

