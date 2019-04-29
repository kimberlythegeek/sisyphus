#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

#
# options processing
#
options="d:n"
function usage()
{
    cat <<EOF
usage: 
$SCRIPT -d directory [-n] 

-d directory    directory to be created.
-n              never prompt when removing existing directory.

Attempts to safely create an empty directory. If -n is not
specified, the script will prompt before deleting any files 
or directories. If -n is specified, it will not prompt.

The safety measures include refusing to run if run by user
root and by refusing to create directories unless there are 
a subdirectory of /tmp or have at least two ancestor 
directories... /grandparent/parent/child.

******************** WARNING ********************
This script will destroy existing directories and
their contents. It can potentially wipe out your
disk. Use with caution.
******************** WARNING ********************

EOF
    exit $ERR_ARGS
}

unset directory

rmopt="-i"

while getopts $options optname ; 
  do 
  case $optname in
      d) directory=$OPTARG;;
      n) unset rmopt;;
  esac
done

source $TEST_DIR/bin/library.sh

if [[ -z $directory ]]
    then
    usage
fi

if [[ `whoami` == "root" ]]; then
    error "can not be run as root" $LINENO
fi

echo "get the canonical directory name for $directory"

tries=1
while ! mkdir -p "$directory"; do
    let tries=tries+1
    if [[ "$tries" -gt $TEST_STARTUP_TRIES ]]; then
        error "Failed to mkdir -p $directory" $LINENO
    fi
    sleep 30
done

if ! pushd "$directory" ; then 
    error "$directory is not accessible" $LINENO
fi

directory=`pwd`
popd

echo "canonical directory name is $directory"

if [[ "$directory" == "/" ]]; then
    error "directory $directory can not be root" $LINENO
fi

parent=`dirname "$directory"`
echo "parent directory is $parent"

grandparent=`dirname "$parent"`
echo "grandparent directory is $grandparent"

if [[ "$parent" != "/tmp" && ( "$parent" == "/" || "$grandparent" == "/" ) ]]; then
    error "directory $directory can not be a subdirectory of $parent" $LINENO
fi

# clean the directory if requested
tries=1
while ! (rm -fR $rmopt $directory && mkdir -p "$directory"); do
    let tries=tries+1
    if [[ "$tries" -gt $TEST_STARTUP_TRIES ]]; then
        error "Failed to rm -fR $rmopt $directory && mkdir -p $directory" $LINENO
    fi
    sleep 30
done
