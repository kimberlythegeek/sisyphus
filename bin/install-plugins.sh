#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

#
# options processing
#
options="p:b:x:D:d:"
function usage()
{
    cat <<EOF
usage:
$SCRIPT -p product -b branch -x executablepath -D directory [-d datafiles]

variable            description
===============     ============================================================
-p product          required. firefox.
-b branch           required. one of supported branches. see library.sh
-x executablepath   required. path to browser executable
-D directory        required. path to location of plugins/components
-d datafiles        optional. one or more filenames of files containing
                    environment
                    variable definitions to be included.

note that the environment variables should have the same names as in the
"variable" column.

EOF
    exit $ERR_ARGS
}

unset product branch executablepath directory datafiles

while getopts $options optname ;
  do
  case $optname in
      p) product=$OPTARG;;
      b) branch=$OPTARG;;
      x) executablepath=$OPTARG;;
      D) directory=$OPTARG;;
      d) datafiles=$OPTARG;;
  esac
done

source $TEST_DIR/bin/library.sh

# include environment variables
loadata $datafiles

if [[ -z "$product" || -z "$branch" || \
    -z "$executablepath" || -z "$directory" ]]; then
    usage
fi

checkProductBranch $product $branch

executable=`get_executable $product $branch $executablepath`

executablepath=`dirname $executable`

#
# install plugins and components
#
echo "$SCRIPT: installing plugins from $directory/ in $executablepath/"
cp -r "$directory/$OSID/" "$executablepath/"
