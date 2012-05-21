#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is mozilla.org code.
#
# The Initial Developer of the Original Code is
# Mozilla Corporation.
# Portions created by the Initial Developer are Copyright (C) 2006.
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#  Bob Clary <bob@bclary.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

#
# options processing
#
options="p:b:x:f:d:"
function usage()
{
    cat <<EOF
usage:
$SCRIPT -p product -b branch  -x executablepath -f filename [-d datafiles]

variable            description
===============     ============================================================
-p product          required. firefox.
-b branch           required. supported branch. see library.sh
-x executablepath   required. directory where to install build
-f filename         required. path to filename where installer is stored
-d datafiles        optional. one or more filenames of files containing
                    environment variable definitions to be included.

note that the environment variables should have the same names as in the
"variable" column.

EOF
    exit $ERR_ARGS
}

unset product branch executablepath filename datafiles

while getopts $options optname ;
do
    case $optname in
        p) product=$OPTARG;;
        b) branch=$OPTARG;;
        x) executablepath=$OPTARG;;
        f) filename=$OPTARG;;
        d) datafiles=$OPTARG;;
    esac
done

source $TEST_DIR/bin/library.sh

# include environment variables
loaddata $datafiles

if [[ -z "$product" || -z "$branch" || -z "$executablepath" || -z "$filename" ]]
then
    usage
fi

$TEST_DIR/bin/uninstall-build.sh -p "$product" -b "$branch" -x "$executablepath"

$TEST_DIR/bin/create-directory.sh -d "$executablepath" -n

filetype=`file $filename`

if [[ $OSID == "nt" ]]; then

    if echo $filetype | grep -q " executable "; then
        chmod u+x "$filename"
        $filename /S /D=`cygpath -a -w "$executablepath"`
    elif echo  $filetype | grep -iq 'zip archive'; then
        tmpdir=`mktemp  -d /tmp/firefoxzip.XXXX` || error "mktemp failed" $LINENO
        # paranoia
        if [[ -z "$tmpdir" ]]; then
            error "empty temp directory" $LINENO
        fi
        mkdir -p "$executablepath"
        unzip -o -d "$tmpdir" "$filename"
        mv $tmpdir/firefox/* "$executablepath/"
        rm -fR "$tmpdir/firefox"
        rmdir "$tmpdir"

        find $executablepath -name '*.exe' | xargs chmod u+x
        find $executablepath -name '*.dll' | xargs chmod u+x
    else
        error "$unknown file type $filetype" $LINENO
    fi

else

    case "$OSID" in
        linux)
            if echo $filetype | grep -iq 'bzip2'; then
                tar --strip-components 1 -jxvf $filename -C "$executablepath"
            elif echo $filetype | grep -iq 'gzip'; then
                tar --strip-components 1 -zxvf $filename -C "$executablepath"
            else
                error "unknown file type $filetype" $LINENO
            fi
            ;;

        darwin)
            # assumes only 1 mount point
            mkdir -p /tmp/sisyphus/mount
            if ! hdiutil attach -mountpoint /tmp/sisyphus/mount $filename; then
                error "mounting disk image" $LINENO
            fi

            for app in /tmp/sisyphus/mount/*.app; do
                cp -R $app $executablepath
            done

            # requires 10.4 or later
            hdiutil detach /tmp/sisyphus/mount
            ;;
    esac

    #
    # patch unix-like startup scripts to exec instead of
    # forking new processes
    #
    executable=`get_executable $product $branch $executablepath`

    executabledir=`dirname $executable`

    cd "$executabledir"
    if [ -e "$product" ]; then
        if file "$product" | grep shell; then
            echo "$SCRIPT: patching $product"
            sed -i.bak 's|^\"$dist_bin/run-mozilla.sh|exec $dist_bin/run-mozilla.sh|' $product
        fi
    fi
    if [ -e run-mozilla.sh ]; then
        echo "$SCRIPT: patching run-mozilla.sh"
        tab=`echo -e '\t'` && sed -i.bak "s|^\([$tab ]*\)\"\$prog|\1exec \"\$prog|" run-mozilla.sh
    fi
fi
