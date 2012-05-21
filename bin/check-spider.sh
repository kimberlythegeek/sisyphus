#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

#
# options processing
#
options="p:b:x:N:d:"
function usage()
{
    cat <<EOF
usage:
$SCRIPT -p product -b branch -x executablepath -N profilename
       [-d datafiles]

variable            description
===============     ============================================================
-p product          required. firefox
-b branch           required. supported branch. see library.sh
-x executablepath   required. directory-tree containing executable named
                    'product'
-N profilename      required. name of profile to be used
-d datafiles        optional. one or more filenames of files containing
                    environment variable definitions to be included.

note that the environment variables should have the same names as in the
"variable" column.

Checks if the Spider extension is installed either in the named profile
or as a global extension, by attempting up to 3 times to launch the Spider.

If this script is called with invalid arguments it returns exit code $ERR_ARGS.
If Spider fails to launch, the script returns exit code $ERR_ERROR.

EOF
    exit $ERR_ARGS
}

unset product branch executablepath profilename datafiles

while getopts $options optname ;
  do
  case $optname in
      p) product=$OPTARG;;
      b) branch=$OPTARG;;
      x) executablepath=$OPTARG;;
      N) profilename=$OPTARG;;
      d) datafiles=$OPTARG;;
  esac
done

source $TEST_DIR/bin/library.sh

# include environment variables
loaddata $datafiles

if [[ -z "$product" || -z "$branch" || -z "$executablepath" || -z "$profilename" ]];
    then
    usage
fi

checkProductBranch $product $branch

executable=`get_executable $product $branch $executablepath`

if echo "$profilename" | egrep -qiv '[a-z0-9_]'; then
    error "profile name must consist of letters, digits or _" $LINENO
fi

echo # attempt to force Spider to load

tries=1
while ! $TEST_DIR/bin/timed_run.py ${TEST_STARTUP_TIMEOUT} "Start Spider: try $tries" \
     $EXECUTABLE_DRIVER \
    "$executable" -P "$profilename" \
    -spider -start -quit \
    -uri "http://${TEST_HTTP}/bin/start-spider.html" \
    -hook "http://${TEST_HTTP}/bin/userhook-checkspider.js"; do
  let tries=tries+1
  if [ "$tries" -gt $TEST_STARTUP_TRIES  ]; then
      error "Failed to start spider. Exiting..." $LINENO
  fi
  sleep 30
done
