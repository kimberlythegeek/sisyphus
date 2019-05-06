#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

source $TEST_DIR/bin/set-build-env.sh $@

if [[ -z "$BUILDTREE" ]]; then
    error "source tree not specified!" $LINENO
fi

case $branch in
    1.9.0);;
    *)
        if [[ -z "$TEST_MOZILLA_HG" ]]; then
            error "environment variable TEST_MOZILLA_HG must be set to the hg repository for branch $branch"
        fi
        ;;
esac

if [[ -n "$TEST_MOZILLA_HG" ]]; then
    # maintain a local copy of the hg repository
    # clone specific trees from it.

    TEST_MOZILLA_HG_LOCAL=${TEST_MOZILLA_HG_LOCAL:-$BUILDDIR/hg.mozilla.org/`basename $TEST_MOZILLA_HG`}

    if [[ ! -d $BUILDDIR/hg.mozilla.org ]]; then
        mkdir $BUILDDIR/hg.mozilla.org
    fi

    if [[ ! -d $TEST_MOZILLA_HG_LOCAL ]]; then
        if ! hg clone $TEST_MOZILLA_HG $TEST_MOZILLA_HG_LOCAL; then
            error "during hg clone of $TEST_MOZILLA_HG" $LINENO
        fi
    fi

    cd $TEST_MOZILLA_HG_LOCAL
    hg pull
    if [[ "$OSID" == "nt" ]]; then
        # remove spurious lock file
        rm -f $TEST_MOZILLA_HG_LOCAL/.hg/wlock.lnk
    fi
    hg update -C
    if [[ "$OSID" == "nt" ]]; then
        # remove spurious lock file
        rm -f $TEST_MOZILLA_HG_LOCAL/.hg/wlock.lnk
    fi
    echo "`hg root` id `hg id`"
fi

mkdir -p $BUILDTREE
cd $BUILDTREE

if [[ -n "$TEST_MOZILLA_HG" ]]; then

    if [[ ! -d mozilla/.hg ]]; then
        if ! hg clone $TEST_MOZILLA_HG_LOCAL $BUILDTREE/mozilla; then
            error "during hg clone of $TEST_MOZILLA_HG_LOCAL" $LINENO
        fi
    fi

    cd mozilla
    if [[ "$OSID" == "nt" ]]; then
        # remove spurious lock file
        rm -f $TEST_MOZILLA_HG_LOCAL/.hg/wlock.lnk
    fi
    if [[ -d .hg/patches && -n "`hg qapplied`" ]]; then
        # qpop any mq patches before pulling from the local repo.
        if ! hg qpop -a; then
            error "during hg qpop of patch queue of $project tree" $LINENO
        fi
    fi
    hg pull
    if [[ "$OSID" == "nt" ]]; then
        # remove spurious lock file
        rm -f $TEST_MOZILLA_HG/.hg/wlock.lnk
    fi
    hg update -C
    if [[ "$OSID" == "nt" ]]; then
        # remove spurious lock file
        rm -f $TEST_MOZILLA_HG_LOCAL/.hg/wlock.lnk
    fi

    hg update -r $TEST_MOZILLA_HG_REV
    if [[ "$OSID" == "nt" ]]; then
        # remove spurious lock file
        rm -f $TEST_MOZILLA_HG_LOCAL/.hg/wlock.lnk
    fi

    echo "`hg root` id `hg id`"

    if [[ -n "$DATE_CO_FLAGS" ]]; then
        eval hg update $DATE_CO_FLAGS
        if [[ "$OSID" == "nt" ]]; then
            # remove spurious lock file
            rm -f $TEST_MOZILLA_HG_LOCAL/.hg/wlock.lnk
        fi
        echo "Update to date $MOZ_CO_DATE `hg root` id `hg id`"
    fi

    echo "build changeset: `hg root` id `hg id`"

fi

case $product in
    firefox|fennec)
        case $branch in
            1.9.0)
                if [[ ! ( -d mozilla && \
                    -e mozilla/client.mk && \
                    -e "mozilla/$project/config/mozconfig" ) ]]; then
                    if ! eval cvs -z3 -q co $MOZ_CO_FLAGS $BRANCH_CO_FLAGS $DATE_CO_FLAGS \
                        mozilla/client.mk mozilla/$project/config/mozconfig; then
                        error "during checkout of $project mozconfig" $LINENO
                    fi
                fi
                if ! $TEST_DIR/bin/set-build-env.sh $@ -c "${MAKE} -f client.mk checkout" 2>&1; then
                    error "during checkout of $project tree" $LINENO
                fi
                ;;

            *)
                # do not use mozilla-build on windows systems as we
                # must use the cygwin python with the cygwin mercurial.

                if ! python client.py checkout; then
                    error "during checkout of $project tree" $LINENO
                fi

                if [[ -d .hg/patches ]]; then
                    # reapply any mq patches before building.
                    if ! hg qpush -a; then
                        error "during hg qpush of patch queue of $project tree" $LINENO
                    fi
                fi
                ;;
        esac
        ;;

    js)

        case $branch in
            1.9.0)
                if [[ ! ( -d mozilla && \
                    -e mozilla/js && \
                    -e mozilla/js/src ) ]]; then
                    if ! eval cvs -z3 -q co $MOZ_CO_FLAGS $BRANCH_CO_FLAGS $DATE_CO_FLAGS mozilla/js; then
                        error "during initial co $MOZ_CO_FLAGS $BRANCH_CO_FLAGS $DATE_CO_FLAGS mozilla/js"
                    fi
                fi

                cd mozilla/js/src

                if ! eval cvs -z3 -q update $MOZ_CO_FLAGS $BRANCH_CO_FLAGS $DATE_CO_FLAGS -d -P 2>&1; then
                    error "during update $MOZ_CO_FLAGS $BRANCH_CO_FLAGS $DATE_CO_FLAGS js/src" $LINENO
                fi

                if ! cvs -z3 -q update -d -P -A editline config  2>&1; then
                    error "during checkout of js/src" $LINENO
                fi
                ;;

            *)

                # do not use mozilla-build on windows systems as we
                # must use the cygwin python with the cygwin mercurial.

                if ! python client.py checkout; then
                    error "during checkout of $project tree" $LINENO
                fi

                if [[ -d .hg/patches ]]; then
                    # reapply any mq patches before building.
                    if ! hg qpush -a; then
                        error "during hg qpush of patch queue of $project tree" $LINENO
                    fi
                fi

                cd js/src
                ;;
        esac
        # end for js shell
        ;;
    *)
        error "unknown product $product" $LINENO
        ;;
esac
