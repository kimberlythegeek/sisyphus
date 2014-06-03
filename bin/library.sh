# -*- Mode: Shell-script; tab-width: 2; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

# This script contains a number of variables, functions, etc which
# are reused across a number of scripts. It should be included in each
# script prior to any other commands as follows:
#
# source $TEST_DIR/bin/library.sh

if [[ -n "$DEBUG" ]]; then
    echo "calling $0 $@" 1>&2
fi

# export variables
set -a

# define our own exit codes to prevent confusion about their meanings
# See Advanced Bash Scripting Guide Chapter 6 Exit and Exit Status and
# Table D1
ERR_TIMED_RUN_OS=66
ERR_TIMED_RUN_SIGNAL=77
ERR_TIMED_RUN_TIMEOUT=88
ERR_TIMED_RUN_INTERRUPT=99
ERR_SIGNAL_KILL=137
ERR_ERROR=100
ERR_ARGS=101

# emit a call stack for function and source calls
function debug_frames() {
  local frame=0
  while caller $frame; do let frame=frame+1; done
}

# in the event of an untrapped script error tail the test log,
# if it exists, to stderr then echo a FATAL ERROR message to the
# test log and stderr.

function _err()
{
    local rc=$?
    debug_frames
    debug "_err: $0"

    case "$rc" in
        0|$ERR_TIMED_RUN_OS|$ERR_TIMED_RUN_SIGNAL|$ERR_TIMED_RUN_TIMEOUT|$ERR_TIMED_RUN_INTERRUPT)
            # ignore exit codes from timed_run.py?
            ;;
        1)
            # Do not treat exit 1 as a fatal error
            ;;
        $ERR_SIGNAL_KILL)
            # terminated by kill.
            if [[ -n "$TEST_LOG" ]]; then
                echo -e "\nKILLED $0 exit code $rc\n" >> $TEST_LOG
            else
                echo -e "\nKILLED $0 exit code $rc\n" 1>&2
            fi
            ;;
        *)
            if [[ -n "$TEST_LOG" ]]; then
                echo -e "\nFATAL ERROR in $0 exit code $rc\n" >> $TEST_LOG
            else
                echo -e "\nFATAL ERROR in $0 exit code $rc\n" 1>&2
            fi
            ;;
    esac
    exit $rc
}

trap "_err" ERR

function _exit()
{
    local rc=$?
    local currscript=`get_scriptname $0`

    debug "_exit: $0"

    if [[ "$rc" -gt 0 && -n "$TEST_LOG" && "$SCRIPT" == "$currscript" ]]; then
        # only tail the log once at the top level script
        tail $TEST_LOG 1>&2
    fi
}

trap "_exit" EXIT

# error message
# output error message end exit $ERR_ERROR

error()
{
    local message=$1
    local lineno=$2

    debug "error: $0:$LINENO"

    echo -e "FATAL ERROR in script $0:$lineno $message\n" 1>&2
    if [[ "$0" == "-bash" || "$0" == "bash" ]]; then
        return 0
    fi
    exit $ERR_ERROR
}

# convert a.b.c to 100*a + 10*b + c for numeric comparisons.
tonumber() (IFS='. ';let v=0; m=100;digits="$1";for d in $digits; do let v=v+d*m; let m=m/10; done; echo $v)
# compare two numbers
lessthan() (if [[ `tonumber $1` -lt `tonumber $2` ]]; then return 0; else return 1; fi )


if [[ -z "$LIBRARYSH" ]]; then
    # skip remainder of script if it has already included

    checkProductBranch()
    {
        local product=$1
        local branch=$2

        case $product in
            js|firefox|fennec)
                ;;
            *)
                error "product \"$product\" must be one of js, firefox, fennec" $LINENO
        esac

        case $branch in
            release|beta|aurora|nightly|inbound)
                ;;
            *)
                error "branch \"$branch\" must be one of release beta aurora nightly inbound" $LINENO
        esac

     }

    # Darwin 8.11.1's |which| does not return a non-zero exit code if the
    # program can not be found. Therefore, kludge around it.
    findprogram()
    {
        local program=$1
        local location=`which $program 2>&1`
        if [[ ! -x $location ]]; then
            return 1
        fi
        return 0
    }

    debug()
    {
        if [[ -n "$DEBUG" ]]; then
            echo "DEBUG: $@"
        fi
    }

    # console msg
    #
    # output message to console, ie. stderr

    console()
    {
        echo -e "$@" 1>&2
    }

    # loaddata
    #
    # load data files into environment
    loaddata()
    {
        local datafiles="$@"
        local datafile
        if [[ -n "$datafiles" ]]; then
            for datafile in $datafiles; do
                if [[ ! -e "$datafile" ]]; then
                    error "datafile $datafile does not exist"
                fi
                cat $datafile | sed 's|^|data: |'
                if ! source $datafile; then
                    error "Unable to load data file $datafile"
                fi
            done
        fi
    }

    # dumpenvironment
    #
    # output environment to stdout

    dumpenvironment()
    {
        set | grep -v '^SISYPHUS_' | grep '^[A-Za-z]' | sed 's|^|environment: |'
    }

    dumphardware()
    {
        echo "uname -a:`uname -a`"
        echo "uname -s:`uname -s`"
        echo "uname -n:`uname -n`"
        echo "uname -r:`uname -r`"
        echo "uname -v:`uname -v`"
        echo "uname -m:`uname -m`"
        echo "uname -p:`uname -p`"
        if [[ "$OSID" != "darwin" ]]; then
            echo "uname -i:`uname -i`"
            echo "uname -o:`uname -o`"
        fi

        ulimit -a | sed 's|^|ulimit:|'

        if [[ -e /proc/cpuinfo ]]; then
            cat /proc/cpuinfo | sed 's|^|cpuinfo:|'
        fi
        if [[ -e /proc/meminfo ]]; then
            cat /proc/meminfo | sed 's|^|meminfo:|'
        fi
        if findprogram system_profiler; then
            system_profiler | sed 's|^|system_profiler:|'
        fi
    }

    # dumpvars varname1, ...
    #
    # dumps name=value pairs to stdout for each variable named
    # in argument list

    dumpvars()
    {
        local argc=$#
        local argn=1

        while [ $argn -le $argc ]; do
            local var=${!argn}
            echo ${var}=${!var}
            let argn=argn+1
        done
    }

    # get_executable product branch directory
    #
    # writes path to product executable to stdout

    get_executable()
    {
        local get_executable_product="$1"
        local get_executable_branch="$2"
        local get_executable_directory="$3"

        if [[ -z "$get_executable_product" || \
            -z "$get_executable_branch" || \
            -z "$get_executable_directory" ]]; then
            error "usage: get_executable product branch directory"
        elif [[ ! -d "$get_executable_directory" ]]; then
            error "get_executable: executable directory \"$get_executable_directory\" does not exist"
        else
            # should use /u+x,g+x,a+x but mac os x uses an obsolete find
            # filter the output to remove extraneous file in dist/bin for
            # cvs builds on mac os x.
            local executable=`(
                get_executable_name="$get_executable_product${EXE_EXT}"
                case "$OSID" in
                    darwin)
                        get_executable_filter="/[a-zA-Z]*\.app/Contents/MacOS/+$get_executable_product"
                        get_executable_name="$get_executable_name-bin"
                        perm=+111
                        ;;
                    *)
                        get_executable_filter="$get_executable_product"
                        perm=/111
                        ;;
                esac
                if find "$get_executable_directory" -perm $perm -type f \
                    -name "$get_executable_name" | \
                    grep -E "$get_executable_filter"; then
                    true
                fi
                )`

            if [[ -z "$executable" ]]; then
                error "get_executable_name=$get_executable_name get_executable_filter=$get_executable_filter get_executable product=$get_executable_product branch=$get_executable_branch directory=$get_executable_directory returned empty path" $LINENO
                error "get_executable $get_executable_product $get_executable_branch $get_executable_directory returned empty path" $LINENO
            fi

            if [[ ! -x "$executable" ]]; then
                # custom builds of Firefox on Linux have two not easily distinguishable executables.
                # check each and pick the last executable choice which in most cases will be dist/bin/firefox.
                local executable_list="$executable"
                local executable_temp
                for executable_temp in $executable_list; do
                    if [[ -x "$executable_temp" ]]; then
                        executable="$executable_temp"
                    fi
                done
                if [[ ! -x "$executable" ]]; then
                    error "executable \"$executable\" is not executable" $LINENO
                fi
            fi

            echo $executable
        fi
    }

    function get_scriptname()
    {
        debug "\$0: $0"

        local script
        if [[ "$0" == "-bash" || "$0" == "bash" ]]; then
            script="library.sh"
        else
            script=`basename $0`
        fi
        echo $script
    }

    xbasename()
    {
        local path=$1
        local suffix=$2
        local result

        if ! result=`basename -s $suffix $path 2>&1`; then
            result=`basename $path $suffix`
        fi

        echo $result
    }

    LIBRARYSH=1

    MALLOC_CHECK_=${MALLOC_CHECK_:-0}

    ulimit -c 0

    # set path to make life easier
    if ! echo ${PATH} | grep -q $TEST_DIR/bin; then
        PATH=$TEST_DIR/bin:$PATH
    fi

    # force en_US locale
    if ! echo "$LANG" | grep -q en_US; then
        LANG=en_US
        LC_TIME=en_US
    fi

    # handle sorting non-ascii logs on mac os x 10.5.3
    LC_ALL=C

    TEST_TIMEZONE=`date +%z`

    # save starting directory
    STARTDIR=`pwd`

    # location of the script.
    SCRIPTDIR=`dirname $0`

    # don't attach to running instance
    MOZ_NO_REMOTE=1

    # don't restart
    NO_EM_RESTART=1

    # bypass profile manager
    MOZ_BYPASS_PROFILE_AT_STARTUP=1

    # ah crap handler timeout
    MOZ_GDB_SLEEP=${MOZ_GDB_SLEEP:-10}

    #MOZ_CRASHREPORTER_DISABLE=${MOZ_CRASHREPORTER_DISABLE:-1}
    MOZ_CRASHREPORTER_NO_REPORT=${MOZ_CRASHREPORTER_NO_REPORT:-1}

    #leak gauge
    #NSPR_LOG_MODULES=DOMLeak:5,DocumentLeak:5,nsDocShellLeak:5

    # disable due to hangs on Windows 7
    #TEST_MEMORY="`memory.pl`"

    # debug msg
    #
    # output debugging message to stdout if $DEBUG is set

    DEBUG=${DEBUG:-""}

    SCRIPT=`get_scriptname $0`

    if [[ -z "$TEST_DIR" ]]; then
        # get the "bin" directory
        TEST_DIR=`dirname $0`
        # get the "bin" directory parent
        TEST_DIR=`dirname $TEST_DIR`
        if [[ ! -e "${TEST_DIR}/bin/library.sh" ]]; then
            error "BAD TEST_DIR $TEST_DIR"
        fi
    fi

    TEST_HTTP=${TEST_HTTP:-test.mozilla.com}
    TEST_STARTUP_TIMEOUT=${TEST_STARTUP_TIMEOUT:-60}
    TEST_STARTUP_TRIES=${TEST_STARTUP_TRIES:-3}
    TEST_MACHINE=`uname -n`

    kernel_name=`uname -s`

    if [[ $kernel_name == 'Linux' ]]; then
        OSID=linux
        EXE_EXT=
        TEST_KERNEL=`uname -r | sed 's|\([0-9]*\)\.\([0-9]*\)\.\([0-9]*\).*|\1.\2.\3|'`
        TIMECOMMAND='/usr/bin/time -f "Elapsed time %e seconds, User %U seconds, System %S seconds, CPU %P, Memory: %M"'

        if [[ -n "$TEST_PROCESSORTYPE" ]]; then
            # Allow processor type to be overridden by environment variable.
            # intel32, intel64, amd32, amd64
            case "$TEST_PROCESSORTYPE" in
                intel32|intel64|amd32|amd64)
                    ;;
                *)
                    error "Unsupported processor type $TEST_PROCESSORTYPE"
                    ;;
            esac
        else
            TEST_PROCESSORTYPE=`cat /proc/cpuinfo | grep vendor | uniq | sed 's|vendor.* : \(.*\)|\1|'`
            if echo $TEST_PROCESSORTYPE | grep -q 'Intel'; then
                TEST_PROCESSORTYPE=intel
            elif echo $TEST_PROCESSORTYPE | grep -q 'AMD'; then
                TEST_PROCESSORTYPE=amd
            else
                error "Unsupported processor type $TEST_PROCESSORTYPE"
            fi

            if uname -p | grep -q '64$'; then
                TEST_PROCESSORTYPE=${TEST_PROCESSORTYPE}64
            else
                TEST_PROCESSORTYPE=${TEST_PROCESSORTYPE}32
            fi
        fi
    elif [[ $kernel_name == 'Darwin' ]]; then
        OSID=darwin
        EXE_EXT=
        TEST_KERNEL=`uname -r`
        TIMEFORMAT="Elapsed time %E seconds, User %U seconds, System %S seconds, CPU %P%"
        TIMECOMMAND=time

        if [[ -n "$TEST_PROCESSORTYPE" ]]; then
            # Allow processor type to be overridden by environment variable.
            # intel32, intel64
            case "$TEST_PROCESSORTYPE" in
                intel32|intel64)
                    ;;
                *)
                    error "Unsupported processor type $TEST_PROCESSORTYPE"
                    ;;
            esac
        else
            TEST_PROCESSORTYPE=`uname -p`
            if [[ $TEST_PROCESSORTYPE == "i386" ]]; then
                TEST_PROCESSORTYPE=intel
            else
                error "Unsupported processor type $TEST_PROCESSORTYPE"
            fi

            if lessthan $TEST_KERNEL 9.8.0; then
                error "Unsupported kernel $TEST_KERNEL"
            elif lessthan $TEST_KERNEL 10.8.0; then
                # Mac OS X 10.5 (9.8.0) only supports 32 bit builds
                TEST_PROCESSORTYPE=${TEST_PROCESSORTYPE}32
            else
                # Default Mac OS X 10.6 and later to 64 bit builds
                TEST_PROCESSORTYPE=${TEST_PROCESSORTYPE}64
            fi
        fi

    elif echo $kernel_name | grep -q CYGWIN; then
        OSID=nt
        EXE_EXT=".exe"
        TEST_KERNEL=`echo $kernel_name | sed 's|[^.0-9]*\([.0-9]*\).*|\1|'`
        TIMECOMMAND='/usr/bin/time -f "Elapsed time %e seconds, User %U seconds, System %S seconds, CPU %P, Memory: %M"'

        if [[ -n "$TEST_PROCESSORTYPE" ]]; then
            # Allow processor type to be overridden by environment variable.
            # intel32, intel64, amd32, amd64
            case "$TEST_PROCESSORTYPE" in
                intel32|intel64|amd32|amd64)
                    ;;
                *)
                    error "Unsupported processor type $TEST_PROCESSORTYPE"
                    ;;
            esac
        else
            TEST_PROCESSORTYPE=`cat /proc/cpuinfo | grep vendor | uniq | sed 's|vendor.* : \(.*\)|\1|'`
            if echo $TEST_PROCESSORTYPE | grep -q 'Intel'; then
                TEST_PROCESSORTYPE=intel
            elif echo $TEST_PROCESSORTYPE | grep -q 'AMD'; then
                TEST_PROCESSORTYPE=amd
            fi

            if uname | grep -q '64$'; then
                TEST_PROCESSORTYPE=${TEST_PROCESSORTYPE}64
            else
                TEST_PROCESSORTYPE=${TEST_PROCESSORTYPE}32
            fi
        fi

    else
        error "Unknown OS $kernel_name" $LINENO
    fi

    case $TEST_PROCESSORTYPE in
        *32)
            if [[ $TEST_MEMORY -gt 4 ]]; then
                TEST_MEMORY=4
            fi
            ;;
    esac

    # no dialogs on asserts
    XPCOM_DEBUG_BREAK=${XPCOM_DEBUG_BREAK:-warn}

    if [[ -z "$BUILDDIR" ]]; then
        case `uname -s` in
            MINGW*)
                export BUILDDIR=/c/work/mozilla/builds
                ;;
            *)
                export BUILDDIR=/work/mozilla/builds
                ;;
        esac
    fi
fi
