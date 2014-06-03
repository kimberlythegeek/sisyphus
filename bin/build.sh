#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

source $TEST_DIR/bin/set-build-env.sh $@

dumpenvironment

case $product in
    firefox)
        cd $BUILDTREE/mozilla

        if ! $TEST_DIR/bin/set-build-env.sh $@ -c "${PYMAKE} -f client.mk build" 2>&1; then
            error "error during build" $LINENO
        fi

        case "$OSID" in
            mac)
                if [[ "$buildtype" == "debug" ]]; then
                    if [[ "$product" == "firefox" ]]; then
                        executablepath=$product-$buildtype/dist/FirefoxDebug.app/Contents/MacOS
                    fi
                else
                    if [[ "$product" == "firefox" ]]; then
                        executablepath=$product-$buildtype/dist/Firefox.app/Contents/MacOS
                    fi
                fi
                ;;
            linux)
                executablepath=$product-$buildtype/dist/bin
                ;;
        esac

        if [[ "$OSID" != "nt" ]]; then
            #
            # patch unix-like startup scripts to exec instead of
            # forking new processes.
            #
            executable=`get_executable $product $branch $executablepath`

            executabledir=`dirname $executable`

            # patch to use exec to prevent forked processes
            cd "$executabledir"
            if [ -e "$product" ]; then
                if [[ "`file $product`" != *text* ]]; then
                    # See bug https://bugzilla.mozilla.org/show_bug.cgi?id=552864
                    true;
                elif ! grep -q 'exec "\$dist_bin/run-mozilla.sh"' $product; then
                    echo "$SCRIPT: patching $product"
                    cp $TEST_DIR/bin/$product.diff .
                    patch -N -p0 < $product.diff
                fi
            fi
            if [ -e run-mozilla.sh ]; then
                if ! grep -q 'exec "\$prog"' run-mozilla.sh; then
                    echo "$SCRIPT: patching run-mozilla.sh"
                    cp $TEST_DIR/bin/run-mozilla.diff .
                    patch -N -p0 < run-mozilla.diff
                fi
            fi
        fi
        ;;

    fennec)
        cd $BUILDTREE/mozilla

        if ! $TEST_DIR/bin/set-build-env.sh $@ -c "${PYMAKE} -f client.mk build" 2>&1; then
            error "error during build" $LINENO
        fi

        if ! $TEST_DIR/bin/set-build-env.sh $@ -c "${PYMAKE} -C $product-$buildtype package" 2>&1; then
            error "error during build" $LINENO
        fi
        ;;
    js)

        if [[ -e "$BUILDTREE/mozilla/js/src/configure.in" ]]; then

            # use the new fangled autoconf build environment for spidermonkey

            # recreate the OBJ directories to match the old naming standards
            TEST_JSDIR=${TEST_JSDIR:-$TEST_DIR/tests/mozilla.org/js}
            source $TEST_JSDIR/config.sh

            cd "$BUILDTREE/mozilla/js/src"
            mkdir -p "$JS_OBJDIR"

            # run autoconf when configure.in is newer than configure
            if [[ configure.in -nt configure ]]; then
                if [[ "$OSID" == "nt" ]]; then
                    AUTOCONF=autoconf-2.13
                elif findprogram autoconf-2.13; then
                    AUTOCONF=autoconf-2.13
                elif findprogram autoconf2.13; then
                    AUTOCONF=autoconf2.13
                elif findprogram autoconf213; then
                    AUTOCONF=autoconf213
                else
                    error "autoconf 2.13 not detected"
                fi

                if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src; eval \"$AUTOCONF\";" 2>&1; then
                    error "during js/src autoconf" $LINENO
                fi
            fi


            # XXX: Todo
            # This reproduces the limited approach which previously existed with Makefile.ref but
            # does not provide the full functionality provided by the available configure options.
            # Ideally, it would be good to use a mozconfig approach (if available) that would generate
            # the necessary configure command line arguments. This would provide the generality to
            # specify arbitrary configure options.
            #

            if [[ "configure" -nt "$JS_OBJDIR/Makefile" ]]; then
                if [[ "$buildtype" == "debug" ]]; then
                    if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src/$JS_OBJDIR; ../configure --prefix=$BUILDTREE/mozilla/js/src/$JS_OBJDIR  --disable-optimize --enable-debug"; then
                        error "during js/src/$JS_OBJDIR configure" $LINENO
                    fi
                else
                    if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src/$JS_OBJDIR; ../configure --prefix=$BUILDTREE/mozilla/js/src/$JS_OBJDIR  --enable-optimize --disable-debug"; then
                        error "during js/src/$JS_OBJDIR configure" $LINENO
                    fi
                fi
            fi

            if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src/$JS_OBJDIR; make" 2>&1; then
                error "during js/src build" $LINENO
            fi

            if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src/$JS_OBJDIR; make install" 2>&1; then
                error "during js/src install" $LINENO
            fi

        elif [[ -e "$BUILDTREE/mozilla/js/src/Makefile.ref" ]]; then

            # use the old-style Makefile.ref build environment for spidermonkey

            if [[ $buildtype == "debug" ]]; then
                export JSBUILDOPT=
            else
                export JSBUILDOPT=BUILD_OPT=1
            fi

            if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src; make -f Makefile.ref ${JSBUILDOPT} clean" 2>&1; then
                error "during js/src clean" $LINENO
            fi

            if ! $TEST_DIR/bin/set-build-env.sh $@ -c "cd js/src; make -f Makefile.ref ${JSBUILDOPT}" 2>&1; then
                error "during js/src build" $LINENO
            fi

        else
            error "Neither Makefile.ref or autoconf builds available"
        fi
        ;;
esac
