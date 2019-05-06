#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

source $TEST_DIR/bin/set-build-env.sh $@

if [[ ! -e "$BUILDDIR" ]]; then
    echo "build directory \"$BUILDDIR\" doesn't exist, ignoring clobber"
    exit
fi

case $product in
    firefox|fennec)

        if [[ ! -e "$executablepath" ]]; then
            echo "executable path $executablepath doesn't exist, ignoring clobber"
            exit
        fi

        rm -fR $BUILDTREE/mozilla/$product-$buildtype/
        ;;

    js)

        if [[ ! -e "$jsshellsourcepath" ]]; then
            echo "javascript shell source path $jsshellsourcepath doesn't exist, ignoring clobber"
            exit
        fi
        if [[ -e "$BUILDTREE/mozilla/js/src/configure.in" ]]; then
            rm -f $BUILDTREE/mozilla/js/src/configure
        fi
        rm -fR $BUILDTREE/mozilla/js/src/*_*.OBJ
        ;;
esac
