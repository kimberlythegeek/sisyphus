#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

#
# options processing
#
options="p:b:x:N:E:d:"
function usage()
{
    cat <<EOF
usage:
$SCRIPT -p product -b branch -x executablepath -N profilename -E extensiondir
       [-d datafiles]

variable            description
===============     ============================================================
-p product          required. firefox, fennec.
-b branch           required. supported branch. see library.sh
-x executablepath   required. directory-tree containing executable named
                    'product'
-N profilename      required. profile name
-E extensiondir       required. path to directory containing xpis to be installed
-d datafiles        optional. one or more filenames of files containing
            environment variable definitions to be included.

note that the environment variables should have the same names as in the
"variable" column.

EOF
    exit $ERR_ARGS
}

unset product branch executablepath profilename extensiondir datafiles

while getopts $options optname ;
do
    case $optname in
        p) product=$OPTARG;;
        b) branch=$OPTARG;;
        x) executablepath=$OPTARG;;
        N) profilename=$OPTARG;;
        E) extensiondir=$OPTARG;;
        d) datafiles=$OPTARG;;
    esac
done

source $TEST_DIR/bin/library.sh

# include environment variables
loaddata $datafiles

if [[ -z "$product" || -z "$branch" || \
    -z "$executablepath" || -z "$profilename" || -z "$extensiondir" ]]; then
    usage
fi

checkProductBranch $product $branch

if echo $profilename | egrep -qiv '[a-z0-9_]'; then
    error "profile name must consist of letters, digits or _" $LINENO
fi

echo "get executable"
if ! executable=`get_executable $product $branch $executablepath 2>&1`; then
    error "get_executable: $executable" $LINENO
fi

echo "get extensiondir"
if ! executableextensiondir=`dirname $executable 2>&1`/extensions; then
    error "get extensiondir: $executableextensiondir" $LINENO
fi

# create directory to contain installed extensions
if [[ ! -d /tmp/sisyphus/extensions ]]; then
    create-directory.sh -n -d /tmp/sisyphus/extensions
fi

for extensionloc in $extensiondir/all/*.xpi $extensiondir/$OSID/*.xpi; do
    echo "checking $extensiondir"

    if [[ $extensionloc == "$extensiondir/all/*.xpi" ]]; then
        continue
    fi
    if [[ $extensionloc == "$extensiondir/$OSID/*.xpi" ]]; then
        continue
    fi

    extensionname=`xbasename $extensionloc .xpi`
    extensioninstalldir=/tmp/sisyphus/extensions/$extensionname

    if [[ "$OSID" == "nt" ]]; then
        extensionosinstalldir=`cygpath -a -w $extensioninstalldir`
    else
        extensionosinstalldir=$extensioninstalldir
    fi

    echo installing $extensionloc
    # unzip the extension if it does not already exist
    # or if it is newer than the already unpacked version.
    if [[ ! -e $extensioninstalldir || $extensionloc -nt $extensioninstalldir ]]; then
        create-directory.sh -n -d $extensioninstalldir
        unzip -d $extensioninstalldir $extensionloc
    fi

    echo "getting extension uuid"
    extensionuuid=`perl $TEST_DIR/bin/get-extension-uuid.pl $extensioninstalldir/install.rdf`
    if [[ ! -e $executableextensiondir/$extensionuuid ]]; then
        echo $extensionosinstalldir > $executableextensiondir/$extensionuuid
    fi

done

# restart to make extension manager happy
#if ! $TEST_DIR/bin/timed_run.py ${TEST_STARTUP_TIMEOUT} "install extensions - first restart" \
#    $executable -P $profilename "http://${TEST_HTTP}/bin/install-extensions-1.html"; then
#    echo "Ignoring 1st failure to load the install-extensions page"
#fi

if ! $TEST_DIR/bin/timed_run.py ${TEST_STARTUP_TIMEOUT} "install extensions - first restart" \
    $executable -P $profilename -silent ; then
    echo "Ignoring 1st failure to -silent"
fi
exit 0
