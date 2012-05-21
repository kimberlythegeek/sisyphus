#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

#
# options processing
#
options="p:b:B:T:e:d:X:v"
function usage()
{
    cat<<EOF
usage: 
$SCRIPT -p products -b branches -B buildcommands -T buildtypes [-e extra] [-d datafiles] [-v]

variable            description
===============     ===========================================================
-p products         required. one or more of js firefox
-b branches         required. one or more of supported branches. see library.sh.
-B buildcommands    required. one or more of clean clobber checkout build
-T buildtypes       required. one or more of opt debug
-e extra            optional. extra qualifier to pick build tree and mozconfig.
-d datafiles        optional. one or more filenames of files containing 
                    environment variable definitions to be included.
-v                  optional. verbose - copies log file output to stdout.

note that the environment variables should have the same names as in the 
"variable" column.

EOF
    exit $ERR_ARGS
}

unset products branches buildcommands buildtypes extra extraflag datafiles

while getopts $options optname ; 
  do 
  case $optname in
      p) products="$OPTARG";;
      b) branches="$OPTARG";;
      B) buildcommands="$OPTARG";;
      T) buildtypes="$OPTARG";;
      e) extra="-$OPTARG"
          extraflag="-e $OPTARG";;
      d) datafiles=$OPTARG;;
      v) verbose=1;;
      X) processortype="$OPTARG";;
  esac
done

if [[ -n "$processortype" ]]; then
    export TEST_PROCESSORTYPE="$processortype"
fi

source $TEST_DIR/bin/library.sh

TEST_LOG=/dev/null

# include environment variables
loaddata $datafiles

if [[ -z "$products" || -z "$branches" || -z "$buildcommands" || \
    -z "$buildtypes" ]]; then
    usage
fi

# clean first in case checkout changes the configuration
if echo "$buildcommands" | grep -iq clean; then
    for product in $products; do
        for branch in $branches; do

            checkProductBranch $product $branch

            for buildtype in $buildtypes; do

                TEST_DATE=`date -u +%Y-%m-%d-%H-%M-%S``date +%z`
                TEST_LOG="${TEST_DIR}/results/${TEST_DATE},$product,$branch$extra,$buildtype,$OSID,${TEST_MACHINE},clean.log"

                echo "log: $TEST_LOG"

                if [[ "$verbose" == "1" ]]; then
                    clean.sh -p $product -b $branch -T $buildtype $extraflag 2>&1 | tee $TEST_LOG
                else
                    clean.sh -p $product -b $branch -T $buildtype $extraflag > $TEST_LOG 2>&1
                fi
            done
        done
    done
fi

# clobber first in case checkout changes the configuration
if echo "$buildcommands" | grep -iq clobber; then
    for product in $products; do
        for branch in $branches; do

            checkProductBranch $product $branch

            for buildtype in $buildtypes; do

                TEST_DATE=`date -u +%Y-%m-%d-%H-%M-%S``date +%z`
                TEST_LOG="${TEST_DIR}/results/${TEST_DATE},$product,$branch$extra,$buildtype,$OSID,${TEST_MACHINE},clobber.log"

                echo "log: $TEST_LOG"

                if [[ "$verbose" == "1" ]]; then
                    clobber.sh -p $product -b $branch -T $buildtype $extraflag 2>&1 | tee $TEST_LOG
                else
                    clobber.sh -p $product -b $branch -T $buildtype $extraflag > $TEST_LOG 2>&1
                fi
            done
        done
    done
fi

# if checkout, ignore buildtypes
if echo "$buildcommands" | grep -iq checkout; then
    for product in $products; do
        for branch in $branches; do

            checkProductBranch $product $branch

            TEST_DATE=`date -u +%Y-%m-%d-%H-%M-%S``date +%z`
            TEST_LOG="${TEST_DIR}/results/${TEST_DATE},$product,$branch$extra,$buildtype,$OSID,${TEST_MACHINE},checkout.log"

            echo "log: $TEST_LOG"

            if [[ "$verbose" == "1" ]]; then
                checkout.sh -p $product -b $branch -T opt $extraflag 2>&1 | tee $TEST_LOG
            else
                checkout.sh -p $product -b $branch -T opt $extraflag > $TEST_LOG 2>&1
            fi

        done
    done
fi

if echo "$buildcommands" | grep -iq build; then
    for product in $products; do
        for branch in $branches; do
            for buildtype in $buildtypes; do

                checkProductBranch $product $branch

                TEST_DATE=`date -u +%Y-%m-%d-%H-%M-%S``date +%z`
                TEST_LOG="${TEST_DIR}/results/${TEST_DATE},$product,$branch$extra,$buildtype,$OSID,${TEST_MACHINE},build.log"

                echo "log: $TEST_LOG"

                if [[ "$verbose" == "1" ]]; then
                    build.sh -p $product -b $branch -T $buildtype $extraflag 2>&1 | tee $TEST_LOG
                else
                    build.sh -p $product -b $branch -T $buildtype $extraflag > $TEST_LOG 2>&1
                fi

            done
        done
    done
fi
