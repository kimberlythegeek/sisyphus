#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

args=$@
script=`basename $0`

#
# options processing
#
options="u:c:f:t:d:"
function usage()
{
    cat <<EOF
$SCRIPT $args

usage: 
$SCRIPT -u downloadurl [-c credentials] -f filepath [-t timeout] [-d datafiles]

variable            description
===============     ============================================================
-u downloadurl      required. url to download build from
-c credentials      optional. username:password
-f filepath         required. path to filename to store downloaded file
-t timeout          optional. timeout in seconds before download fails.
                    default 300 seconds
-d datafiles        optional. one or more filenames of files containing 
                    environment variable definitions to be included.

note that the environment variables should have the same names as in the 
"variable" column.

downloads file from downloadurl with optional authentication credentials
saving the file to filepath. If the path to the file does not exist,
it is created. If the download takes longer than timeout seconds,
the download is cancelled.

EOF
    exit $ERR_ARGS
}

unset downloadurl credentials filepath timeout datafiles

while getopts $options optname ; 
  do 
  case $optname in
      u) downloadurl=$OPTARG;;
      c) credentials=$OPTARG;;
      f) filepath=$OPTARG;;
      t) timeout=$OPTARG;;
      d) datafiles=$OPTARG;;
  esac
done

source $TEST_DIR/bin/library.sh

# include environment variables
loaddata $datafiles

if [[ -z $downloadurl || -z $filepath ]]
    then
    usage
fi

if [[ -n "$credentials" ]]; then
    auth="--user $credentials"
fi

timeout=${timeout:-300}

path=`dirname "$filepath"`

if [[ -z "$path" ]]; then
    echo "$SCRIPT: ERROR filepath path is empty"
    usage
fi

echo "downloadurl=$downloadurl filepath=$filepath credentials=$credentials timeout=$timeout"

# curl options
# -S show error if failure
# -s silent mode
# -L follow 3XX redirections
# -m $timeout time out 
# -D - dump headers to stdout
# --create-dirs create path if needed

if ! curl -LsS -m $timeout "$downloadurl" -D - --create-dirs -o "$filepath" $auth; then
    error "$SCRIPT: FAIL Unable to download $downloadurl" $LINENO
fi


