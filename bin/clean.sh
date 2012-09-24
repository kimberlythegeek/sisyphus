#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

source $TEST_DIR/bin/set-build-env.sh $@

case $product in
    firefox)

        if ! $TEST_DIR/bin/set-build-env.sh $@ -c "${PYMAKE} -f client.mk clean" 2>&1; then
            error "during client.mk clean" $LINENO
        fi
        ;;

    js)
        if [[ -e "$BUILDTREE/mozilla/js/src/configure.in" ]]; then
            # use the new fangled autoconf build environment for spidermonkey

            # recreate the OBJ directories to match the old naming standards
            TEST_JSDIR=${TEST_JSDIR:-$TEST_DIR/tests/mozilla.org/js}
            source $TEST_JSDIR/config.sh

            mkdir -p "$BUILDTREE/mozilla/js/src/$JS_OBJDIR"

            if [[ ! -e "$BUILDTREE/mozilla/js/src/configure" ]]; then

                if findprogram autoconf-2.13; then
                    AUTOCONF=autoconf-2.13
                elif findprogram autoconf213; then
                    AUTOCONF=autoconf213
                else
                    error "autoconf 2.13 not detected"
                fi

                cd "$BUILDTREE/mozilla/js/src"
                eval "$AUTOCONF"

            fi

            cd "$BUILDTREE/mozilla/js/src/$JS_OBJDIR"

            if [[ -e "Makefile" ]]; then
                if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src/$JS_OBJDIR; make clean" 2>&1; then
                    error "during js/src clean" $LINENO
                fi
            fi

        elif [[ -e "$BUILDTREE/mozilla/js/src/Makefile.ref" ]]; then

            if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src/editline; make -f Makefile.ref clean" 2>&1; then
                error "during editline clean" $LINENO
            fi

            if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src; make -f Makefile.ref clean" 2>&1; then
                error "during SpiderMonkey clean" $LINENO
            fi
        else
            error "Neither Makefile.ref or autoconf builds available"
        fi
        ;;
esac
