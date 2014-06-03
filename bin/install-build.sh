#!/bin/bash -e
# -*- Mode: Shell-script; tab-width: 4; indent-tabs-mode: nil; -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

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
-p product          required. firefox, fennec.
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
        chmod ugo+x "$filename"
        $filename /S /D=`cygpath -a -w "$executablepath"`
    elif echo  $filetype | grep -Eiq '(zip archive|Microsoft OOXML)'; then
        tmpdir=`mktemp  -d /tmp/${product}zip.XXXX` || error "mktemp failed" $LINENO
        # paranoia
        if [[ -z "$tmpdir" ]]; then
            error "empty temp directory" $LINENO
        fi
        mkdir -p "$executablepath"
        unzip -o -d "$tmpdir" "$filename"
        mv $tmpdir/${product}/* "$executablepath/"
        rm -fR "$tmpdir/${product}"
        rmdir "$tmpdir"

        find $executablepath -name '*.exe' | xargs chmod ugo+x
        find $executablepath -name '*.dll' | xargs chmod ugo+x
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
