#!/usr/bin/env bash
set -e

MESSAGE="[CSW merge]"

REMOTES="cbc-tools.git cluster-backbone.git cluster-backbone-sql.git cluster-config-server.git \
        cluster-man-pages.git  cluster-server.git collectd-init.git discovery-server.git \
        host-monitoring.git initcore.git init-license-tools.git init-snmp-libs.git loadmodules.git \
        logcheck-server.git logging-server.git md-config-server.git meta-server.git \
        mother.git package-install.git python-modules-base.git \
        rms-tools.git rms-tools-base.git rrd-grapher.git \
        rrd-server.git webfrontend.git"


TARGET=csw
SOURCES=sources

# Populated by checkout_all_branches
ALL_BRANCHES=""

function message {
    python -c "print '*' * 50"
    echo $1
    python -c "print '*' * 50"
}

function clone_sources {
    message "Cloning all sources"
    rm -rf $SOURCES/*
    for remote in $REMOTES; do
        git clone git@repository:/srv/git/$remote $SOURCES/$remote
    done
}

function checkout_all_branches {
    message "Checking out all branches"
    for remote in $REMOTES; do
        # Don't do this in a subshell - we need to change the
        # environment (ALL_BRANCHES)
        cd $SOURCES/$remote
        git fetch --all --prune
        for branch in $(git branch -r | grep -v master); do
            ALL_BRANCHES="$ALL_BRANCHES\n${branch#origin/}"
            git checkout --track $branch
        done
        git checkout master
        git pull --all
        cd ../..
    done
    ALL_BRANCHES=$(echo -e $ALL_BRANCHES | sort -u)
    # Note: master has to be the first branch in the list
    ALL_BRANCHES="master $ALL_BRANCHES"
}

function remove_conflicting_files {
    message "Removing conflicting files"
    files_to_remove="__init__.py prepare_rpm .gitignore"
    files_to_rename="setup.py"
    for remote in $REMOTES; do
        (
            cd $SOURCES/$remote
            for branch in $(git for-each-ref --format "%(refname:short)" refs/heads); do
                git checkout $branch
                for file in $files_to_remove; do
                    [[ -f $file ]] && git rm $file
                done
                for file in $files_to_rename; do
                    sane_remote=$(echo $remote | cut -f 1 -d .)
                    [[ -f $file ]] && git mv $file ${sane_remote}_$file
                done
                if [[ "$remote" == "webfrontend.git" ]]; then
                    git rm initat/cluster/__init__.py
                fi
                if [[ "$remote" == "rms-tools-base.git" ]]; then
                    for i in $(git ls-files); do
                        keep="n"
                        for to_keep in sgestat.py sge_tools.py; do
                            echo "i: $i to_keep $to_keep"
                            if [[ $i == $to_keep ]]; then
                                keep="y"
                            fi
                        done
                        if [[ $keep == "n" ]]; then
                            git rm -rf $i
                        fi
                    done
                fi
                #git ci -a -m "$MESSAGE: Removed conflicting files"
                git ci -a --amend --no-edit
            done
        )
    done
}

function create_target {
    message "Creating target repository"
    rm -rf $TARGET
    git init $TARGET

    (
        cd $TARGET
        git ci --allow-empty -m "$MESSAGE Initial commit"
        git rev-parse HEAD > INITIAL_HEAD

        for remote in $REMOTES; do
            git remote add $remote ../$SOURCES/$remote
        done

        git fetch --all --prune
    )
}

function perform_merge {
    message "Performing merge"
    if [[ -z "$ALL_BRANCHES" ]]; then
        echo "ALL_BRANCHES is empty! You must at least run checkout_all_branches()"
        exit 1
    fi

    cd $TARGET
    # Create all the branches
    for branch in $ALL_BRANCHES; do
        if [[ $branch == "master" ]]; then
            continue
        fi
        git checkout -b $branch
    done
    for branch in $ALL_BRANCHES; do
        git fetch --all --prune
        git checkout $branch
        branches_to_merge=""
        for remote in $REMOTES; do
            echo $remote/$branch
            if child=$(! git rev-parse $remote/$branch 2>/dev/null); then
                continue
            fi
            child=$(git rev-list --reverse $child | head -1)
            parent=$(cat INITIAL_HEAD)
            # Write grafts only for the master, it is safe to assume all other
            # branches will have the initial commit in master as a common parent.
            # master has to be the first branch in the list.
            if [[ $branch == "master" ]]; then
                echo "$child $parent" >> .git/info/grafts
            fi
            branches_to_merge="$branches_to_merge $remote/$branch"
        done
        git merge -m "$MESSAGE: Merged all repositories (branch $branch)" $branch $branches_to_merge
    done
}

function cleanup {
    message "Performing cleanup"
    git checkout master
    rm INITIAL_HEAD
}


#clone_sources
checkout_all_branches
remove_conflicting_files
create_target
perform_merge
cleanup

