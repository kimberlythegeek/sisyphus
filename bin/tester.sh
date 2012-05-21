#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

$(python $TEST_DIR/bin/limit_memory.py)

#
# options processing
#
options="p:b:e:T:t:X:v"
function usage()
{
    cat<<EOF
usage: 
$SCRIPT -t testscript [-v ] datalist1 [datalist2 [datalist3 [datalist4]]]

variable            description
===============     ===========================================================
-t testscript       required. quoted test script with required arguments.
-X processortype    processor type: intel32, intel64, amd32, amd64, ppc
-v                  optional. verbose - copies log file output to stdout.

executes the testscript using the input data files in 
$TEST_DIR/data constructed from each combination of the input parameters:

{item1},{item2},{item3},{item4}

EOF
    exit $ERR_ARGS
}

unset testscript testargs

# remove script name from args
shiftargs=1

while getopts $options optname ; 
  do 
  case $optname in
      t) 
          let shiftargs=$shiftargs+1
          testscript="$OPTARG"
          if echo $testscript | grep -iq ' ' ; then
              testargs=`echo $testscript   | sed 's|^\([^ ]*\)[ ]*\(.*\)|\2|'`
              testscript=`echo $testscript | sed 's|^\([^ ]*\)[ ]*.*|\1|'`
          fi
          ;;
      v) verbose=1
          let shiftargs=$shiftargs+1
          ;;
      X) processortype="$OPTARG";;

  esac
done

if [[ -z "$testscript" ]]; then
    usage
fi

shift $shiftargs

source $TEST_DIR/bin/library.sh

TEST_LOG=/dev/null

datalist=`combo.sh "$@"`

TEST_SUITE=`dirname $testscript | sed "s|$TEST_DIR/||" | sed "s|/|_|g"`

for data in $datalist; do
    TEST_DATE=`date -u +%Y-%m-%d-%H-%M-%S``date +%z`
    TEST_LOG="${TEST_DIR}/results/${TEST_DATE},$data,$OSID,${TEST_MACHINE},$TEST_SUITE.log"

    if [[ "$OSID" == "nt" ]]; then
        # If on Windows, set up the Windbg/CDB debug log file
        # name to point to our log. 
        export _NT_DEBUG_LOG_FILE="`cygpath -w $TEST_LOG`"
    fi

    # tell caller what the log files are
    echo "log: $TEST_LOG "

    if [[ "$verbose" == "1" ]]; then
        test-setup.sh -d $TEST_DIR/data/$data.data 2>&1 | tee -a $TEST_LOG
    else
        test-setup.sh -d $TEST_DIR/data/$data.data >> $TEST_LOG 2>&1
    fi

    filter=cat

    if [[ "$XPCOM_DEBUG_BREAK" == "stack" ]]; then
        executablepath=$(grep ^environment:.TEST_EXECUTABLEPATH= $TEST_LOG | sed 's|environment: TEST_EXECUTABLEPATH=\(.*\)|\1|')
        symbolspath=$executablepath/crashreporter-symbols

        if [[ -d "$symbolspath" && -e "$TEST_DIR/bin/fix_stack_using_bpsyms.py" ]]; then
            filter="python $TEST_DIR/bin/fix_stack_using_bpsyms.py $symbolspath"
        fi
    fi

    if [[ "$verbose" == "1" ]]; then
        $testscript $testargs -d $TEST_DIR/data/$data.data 2>&1 | $filter | tee -a $TEST_LOG
    else
        $testscript $testargs -d $TEST_DIR/data/$data.data 2>&1 | $filter >> $TEST_LOG 2>&1
    fi

done
