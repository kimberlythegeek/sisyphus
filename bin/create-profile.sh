#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

#
# options processing
#
options="p:b:x:D:N:L:U:d:"
function usage()
{
    cat <<EOF
usage:
$SCRIPT -p product -b branch -x executablepath -D directory -N profilename
       [-L profiletemplate] [-U user] [-d datafiles]

variable            description
===============     ============================================================
-p product          required. firefox.
-b branch           required. supported branch. see library.sh
-x executablepath   required. directory-tree containing executable 'product'
-D directory        required. directory where profile is to be created.
-N profilename      required. profile name
-L profiletemplate  optional. location of a template profile to be used.
-U user             optional. user.js preferences file.
-d datafiles        optional. one or more filenames of files containing
                    environment variable definitions to be included.

note that the environment variables should have the same names as in the
"variable" column.

EOF
    exit $ERR_ARGS
}

unset product branch executablepath directory profilename profiletemplate user datafiles

while getopts $options optname ;
  do
  case $optname in
      p) product=$OPTARG;;
      b) branch=$OPTARG;;
      x) executablepath=$OPTARG;;
      D) directory=$OPTARG;;
      N) profilename=$OPTARG;;
      L) profiletemplate=$OPTARG;;
      U) user=$OPTARG;;
      d) datafiles=$OPTARG;;
  esac
done

source $TEST_DIR/bin/library.sh

# include environment variables
loaddata $datafiles

if [[ -z "$product" || -z "$branch" || -z "$executablepath" || \
    -z "$directory" || -z "$profilename" ]]; then
    usage
fi

checkProductBranch $product $branch

echo "get executable"
if ! executable=`get_executable $product $branch $executablepath 2>&1`; then
    error "get_executable: $executable" $LINENO
fi

$TEST_DIR/bin/create-directory.sh -d "$directory" -n

if echo "$profilename" | egrep -qiv '[a-z0-9_]'; then
    error "profile name \"$profilename\" must consist of letters, digits or _" $LINENO
fi

echo "get directoryospath for $directory"

if [ $OSID == "nt" ]; then
    directoryospath=`cygpath -a -w $directory`
    if [[ -z "$directoryospath" ]]; then
        error "unable to convert unix path to windows path" $LINENO
    fi
else
    directoryospath="$directory"
fi

echo "creating profile $profilename in directory $directory"

tries=1
while ! $TEST_DIR/bin/timed_run.py ${TEST_STARTUP_TIMEOUT} "-" \
        $EXECUTABLE_DRIVER \
        $executable -CreateProfile "$profilename $directoryospath"; do
    let tries=tries+1
    if [[ "$tries" -gt $TEST_STARTUP_TRIES ]]; then
        error "Failed to create profile $directoryospath Exiting..." $LINENO
    fi
    sleep 30
done

if [[ -n $profiletemplate ]]; then
    if [[ ! -d $profiletemplate ]]; then
        error "profile template directory $profiletemplate does not exist" $LINENO
    fi
    echo "copying template profile $profiletemplate to $directory"
    cp -R $profiletemplate/* $directory
fi

if [[ ! -z $user ]]; then
    cp $user $directory/user.js
fi

# work around bug 739682
(if ! $TEST_DIR/bin/timed_run.py ${TEST_STARTUP_TIMEOUT} "silent startup" \
    $executable -P $profilename -silent ; then
    # Delete and recreate the minidumps directory to hide the
    # fatal assertion's minidump from Bughunter.
    $TEST_DIR/bin/create-directory.sh -d "$directory/minidumps/" -n
fi) > /dev/null 2>&1

# force success exit code
echo "exit create-profile.sh"
exit 0
