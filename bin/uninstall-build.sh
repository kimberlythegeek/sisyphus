#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

#
# options processing
#
options="p:b:x:d:"
function usage()
{
    cat <<EOF
usage:
$SCRIPT -p product -b branch  -x executablepath [-d datafiles]

variable            description
===============     ============================================================
-p product          required. firefox.
-b branch           required. supported branch. see library.sh
-x executablepath   required. directory where build is installed
-d datafiles        optional. one or more filenames of files containing
                    environment variable definitions to be included.

note that the environment variables should have the same names as in the
"variable" column.

Uninstalls build located in directory-tree 'executablepath'
then removes the directory upon completion.

EOF
    exit $ERR_ARGS
}

unset product branch executablepath datafiles

while getopts $options optname ;
  do
  case $optname in
      p) product=$OPTARG;;
      b) branch=$OPTARG;;
      x) executablepath=$OPTARG;;
      d) datafiles=$OPTARG;;
  esac
done

source $TEST_DIR/bin/library.sh

# include environment variables
loaddata $datafiles

if [[ -z "$product" || -z "$branch" || -z "$executablepath" ]]
    then
    usage
fi


if ! ls $executablepath/* > /dev/null 2>&1; then
    echo "uninstall-build.sh: ignoring missing $executablepath"
    exit 0
fi

executable=`get_executable $product $branch $executablepath`

executabledir=`dirname $executable`

if [[ $OSID == "nt" ]]; then
    # see http://nsis.sourceforge.net/Docs/Chapter3.html

    # if the directory already exists, attempt to uninstall
    # any existing installation. Suppress failures.

    if [[ -d "$executabledir/uninstall" ]]; then

        uninstalloldexe="$executabledir/uninstall/uninst.exe"
        uninstallnewexe="$executabledir/uninstall/helper.exe"
        if [[ -n "$uninstallnewexe" && -e "$uninstallnewexe" ]]; then
            if $uninstallnewexe /S /D=`cygpath -a -w $executabledir | sed 's@\\\\@\\\\\\\\@g'`; then true; fi
        elif [[ -n "$uninstalloldexe" && -e "$uninstalloldexe" ]]; then
            if $uninstalloldexe /S /D=`cygpath -a -w $executabledir | sed 's@\\\\@\\\\\\\\@g'`; then true; fi
        else
            uninstallexe="$executabledir/$product/uninstall/uninstaller.exe"
            if [[ -n "$uninstallexe" && -e "$uninstallexe" ]]; then
                if $uninstallexe /S /D=`cygpath -a -w "$executabledir"  | sed 's@\\\\@\\\\\\\\@g'`; then true; fi
            fi
        fi

        # the NSIS uninstaller will copy itself, then fork to the new
        # copy so that it can delete itself. This causes a race condition
        # between the uninstaller deleting the files and the rm command below
        # sleep for 10 seconds to give the uninstaller time to complete before
        # the installation directory is removed.
        sleep 10
    fi
fi


# safely creates/deletes a directory. If we pass this,
# then we know it is safe to remove the directory.

$TEST_DIR/bin/create-directory.sh -d "$executablepath" -n

rm -fR "$executablepath"
