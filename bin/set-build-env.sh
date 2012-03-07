#!/bin/bash
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

export MOZ_CVS_FLAGS="-z3 -q"
export MOZILLA_OFFICIAL=1

if [[ -z "$CVSROOT" ]]; then
    if grep -q buildbot@qm ~/.ssh/id_dsa.pub; then
        export CVSROOT=:ext:unittest@cvs.mozilla.org:/cvsroot
        export CVS_RSH=ssh
    else
        export CVSROOT=:pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot
    fi
fi

#
# options processing
#
options="p:b:T:e:c:X:"
usage()
{
    cat <<EOF

usage: set-build-env.sh -p product -b branch -T buildtype [-e extra]

-p product      one of js firefox.
-b branch       one of supported branches. see library.sh
-T buildtype    one of opt debug
-e extra        extra qualifier to pick mozconfig and tree
-X processortype processor type: intel32, intel64, amd32, amd64, ppc
-c commands     quoted text string containing options commands to be
                executed using the build environment's shell.
EOF
}

myexit()
{
    myexit_status=$1

    case $0 in
        *bash*)
            # prevent "sourced" script calls from
            # exiting the current shell.
            break 99;;
        *)
            exit $myexit_status;;
    esac
}

for step in step1; do # dummy loop for handling exits

    unset product branch buildtype extra

    while getopts $options optname ;
      do
      case $optname in
          p) product=$OPTARG;;
          b) branch=$OPTARG;;
          T) buildtype=$OPTARG;;
          e) extra="-$OPTARG";;
          c) commands="$OPTARG";;
          X) processortype="$OPTARG";;
      esac
    done

    if [[ -n "$processortype" ]]; then
        export TEST_PROCESSORTYPE="$processortype"
    fi

    if [[ -z "$LIBRARYSH" ]]; then
        source $TEST_DIR/bin/library.sh
    fi

    # include environment variables
    datafiles=$TEST_DIR/data/$product,$branch$extra,$buildtype.data
    if [[ -e "$datafiles" ]]; then
        loaddata $datafiles
    fi

    # echo product=$product, branch=$branch, buildtype=$buildtype, extra=$extra

    if [[ -z "$product" || -z "$branch" || -z "$buildtype" ]]; then
        echo -n "missing"
        if [[ -z "$product" ]]; then
            echo -n " -p product"
        fi
        if [[ -z "$branch" ]]; then
            echo -n " -b branch"
        fi
        if [[ -z "$buildtype" ]]; then
            echo -n " -T buildtype"
        fi
        usage
        myexit 1
    fi

    if [[ $branch == "1.9.0" ]]; then
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "1.9.1" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/releases/mozilla-1.9.1}
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "1.9.2" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/releases/mozilla-1.9.2}
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "2.0.0" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/releases/mozilla-2.0}
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "release" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/releases/mozilla-release}
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "beta" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/releases/mozilla-beta}
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "aurora" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/releases/mozilla-aurora}
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "nightly" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/mozilla-central}
        export BRANCH_CO_FLAGS="";
    elif [[ $branch == "tracemonkey" ]]; then
        TEST_MOZILLA_HG=${TEST_MOZILLA_HG:-http://hg.mozilla.org/tracemonkey}
        export BRANCH_CO_FLAGS="";
    else
        echo "Unknown branch: $branch"
        myexit 1
    fi

    if [[ -n "$MOZ_CO_DATE" ]]; then
        if [[ $branch == "1.9.0" ]]; then
            export DATE_CO_FLAGS="-D \"$MOZ_CO_DATE\""
        else
            export DATE_CO_FLAGS="--date \"<$MOZ_CO_DATE\""
        fi
    fi

    case $OSID in
        nt)
            # On Windows, Sisyphus is run under Cygwin, so the OS will be CYGWIN
            # regardless. Check if mozilla-build has been installed to the default
            # location, and if so, set up to call mozilla-build to perform the actual
            # build steps.
            #
            # To make life simpler, change the mount point of the C: drive in cygwin from
            # /cygdrive/c to /c via mount -c /
            # which will make paths to non cygwin and non msys locations identical between cygwin
            # and msys, e.g. /c/work will work in both to point to c:\work
            #
            # It is also necessary to set the /tmp path in cygwin and msys to point to the
            # same physical directory.
            #
            # Note that all commands *except* make client.mk will be performed in cygwin.
            #
            # Note that when calling a command string of the form $buildbash --login -c "command",
            # you must cd to the desired directory as part of "command" since msys will set the
            # directory to the home directory prior to executing the command.

            export mozillabuild=${mozillabuild:-/c/mozilla-build}
            export BUILDDIR=${BUILDDIR:-/c/work/mozilla/builds}

            # determine installed compilers
            case "$TEST_PROCESSORTYPE" in
                *32)
                    export HKLM_SOFTWARE="/machine/SOFTWARE"
                    ;;
                *64)
                    export HKLM_SOFTWARE="/machine/SOFTWARE/Wow6432Node"
                    ;;
            esac
            export MSVCROOTKEY="$HKLM_SOFTWARE/Microsoft/VisualStudio"
            export MSVC6KEY="$MSVCROOTKEY/6.0/Setup/Microsoft Visual C++"
            export MSVC71KEY="$MSVCROOTKEY/7.1/Setup/VC"
            export MSVC8KEY="$MSVCROOTKEY/8.0/Setup/VC"
            export MSVC8EXPRESSKEY="$HKLM_SOFTWARE/Microsoft/VCExpress/8.0/Setup/VC"
            export MSVC9KEY="$MSVCROOTKEY/9.0/Setup/VC"
            export MSVC9EXPRESSKEY="$HKLM_SOFTWARE/Microsoft/VCExpress/9.0/Setup/VC"
            export MSVC10KEY="$MSVCROOTKEY/10.0/Setup/VC"

            if [[ -z "$VC6DIR" ]]; then
                export VC6DIR=`regtool get "$MSVC6KEY/ProductDir" 2> /dev/null`
            fi

            if [[ -z "$VC71DIR" ]]; then
                export VC71DIR=`regtool get "$MSVC71KEY/ProductDir" 2> /dev/null`
            fi

            if [[ -z "$VC8DIR" ]]; then
                export VC8DIR=`regtool get "$MSVC8KEY/ProductDir" 2> /dev/null`
            fi

            if [[ -z "$VC8EXPRESSDIR" ]]; then
                export VC8EXPRESSDIR=`regtool get "$MSVC8EXPRESSKEY/ProductDir" 2> /dev/null`
            fi

            if [[ -z "$VC9DIR" ]]; then
                export VC9DIR=`regtool get "$MSVC9KEY/ProductDir" 2> /dev/null`
            fi

            if [[ -z "$VC9EXPRESSDIR" ]]; then
                export VC9EXPRESSDIR=`regtool get "$MSVC9EXPRESSKEY/ProductDir" 2> /dev/null`
            fi

            if [[ -z "$VC10DIR" ]]; then
                export VC10DIR=`regtool get "$MSVC10KEY/ProductDir" 2> /dev/null`
            fi

            # msvc8 official, vc7.1, (2003), vc9 (2009) supported
            # for 1.9.0 and later
            if [[ -n "$VC8DIR" ]]; then
                case "$TEST_PROCESSORTYPE" in
                    *32)
                        startbat=start-msvc8.bat
                        ;;
                    *64)
                        startbat=start-msvc8-x64.bat
                        ;;
                esac
                # set VCINSTALLDIR for use in detecting the MS CRT
                # source when building jemalloc.
                VCINSTALLDIR=$VC8DIR
            elif [[ -n "$VC8EXPRESSDIR" ]]; then
                startbat=start-msvc8.bat
            elif [[ -n "$VC71DIR" ]]; then
                startbat=start-msvc71.bat
            elif [[ -n "$VC9DIR" || -n "$VC9EXPRESSDIR" ]]; then
                case "$TEST_PROCESSORTYPE" in
                    *32)
                        startbat=start-msvc9.bat
                        ;;
                    *64)
                        startbat=start-msvc9-x64.bat
                        ;;
                esac
            elif [[ -n "$VC10DIR" ]]; then
                case "$TEST_PROCESSORTYPE" in
                    *32)
                        startbat=start-msvc10.bat
                        ;;
                    *64)
                        startbat=start-msvc10-x64.bat
                        ;;
                esac
            fi

            if [[ -z "$startbat" ]]; then
                error "startbat is not defined"
            fi

            startbat="$mozillabuild/$startbat"
            if [[ ! -e "$startbat" ]]; then
                error "startbat $startbat does not exist"
            fi

            # The start batch file changes directory and starts an msys bash shell
            # which will block its execution. Create a working copy without the
            # bash invocation to be used to execute commands in the appropriate
            # msys environment from cygwin.
            cmdbat=`echo $startbat | sed 's|start|msys-command|'`;
            if [[ ! -e "$cmdbat" || "$startbat" -nt "$cmdbat" ]]; then
                sed 's|\(^cd.*USERPROFILE.*\)|rem \1|; s|^start /d.*|cmd /c %MOZILLABUILD%\\msys\\bin\\bash --login -i  -c %1|; s|^"%MOZILLABUILD%\\msys\\bin\\bash" --login -i|cmd /c %MOZILLABUILD%\\msys\\bin\\bash --login -i  -c %1|' $startbat > $cmdbat
            fi

            echo moztools Location: $MOZ_TOOLS

            # now convert TEST_DIR and BUILDDIR to cross compatible paths using
            # the common cygdrive prefix for cygwin and msys
            TEST_DIR_WIN=`cygpath -w $TEST_DIR`
            BUILDDIR_WIN=`cygpath -w $BUILDDIR`
            export TEST_DIR=`cygpath -u $TEST_DIR_WIN`
            export BUILDDIR=`cygpath -u $BUILDDIR_WIN`
            ;;

        linux)
            export BUILDDIR=${BUILDDIR:-/work/mozilla/builds}

            # if a 64 bit linux system, assume the
            # compiler is in the standard reference
            # location /tools/gcc/bin/
            case "$TEST_PROCESSORTYPE" in
                *64)
                    export PATH=/tools/gcc/bin:$PATH
                    ;;
            esac
            ;;

        darwin)
            export BUILDDIR=${BUILDDIR:-/work/mozilla/builds}
            ;;
        *)
            ;;
    esac

    export BUILDTREE="${BUILDTREE:-$BUILDDIR/$branch$extra}"

    #
    # extras can't be placed in mozconfigs since not all parts
    # of the build system use mozconfig (e.g. js shell) and since
    # the obj directory is not configurable for them as well thus
    # requiring separate source trees
    #

    case "$extra" in
        -too-much-gc)
            export XCFLAGS="-DWAY_TOO_MUCH_GC=1"
            export CFLAGS="-DWAY_TOO_MUCH_GC=1"
            export CXXFLAGS="-DWAY_TOO_MUCH_GC=1"
            ;;
        -gcov)

            if [[ "$OSID" == "nt" ]]; then
                echo "NT does not support gcov"
                myexit 1
            fi
            export CFLAGS="--coverage"
            export CXXFLAGS="--coverage"
            export XCFLAGS="--coverage"
            export OS_CFLAGS="--coverage"
            export LDFLAGS="--coverage"
            export XLDFLAGS="--coverage"
            export XLDOPTS="--coverage"
            ;;
        -jprof)
            ;;
        -narcissus)
            export XCFLAGS="-DNARCISSUS=1"
            export CFLAGS="-DNARCISSUS=1"
            export CXXFLAGS="-DNARCISSUS=1"
            ;;
    esac

    if [[ ! -d $BUILDTREE ]]; then
        echo "Build directory $BUILDTREE does not exist"
        myexit 2
    fi

    # here project refers to either browser or mail
    # and is used to find mozilla/(browser|mail)/config/mozconfig
    if [[ $product == "firefox" ]]; then
        export project=browser
        export MOZCONFIG=${MOZCONFIG:-"$TEST_DIR/mozconfig/$branch$extra/mozconfig-firefox-$OSID-$TEST_PROCESSORTYPE-$buildtype"}

    else
        echo "Assuming project=browser for product: $product"
        export project=browser
        export MOZCONFIG=${MOZCONFIG:-"$TEST_DIR/mozconfig/$branch$extra/mozconfig-firefox-$OSID-$TEST_PROCESSORTYPE-$buildtype"}
    fi

    if [[ ! -e "$MOZCONFIG" ]]; then
        error "mozconfig $MOZCONFIG does not exist"
    fi
    echo "mozconfig: $MOZCONFIG"
    cat $MOZCONFIG | sed 's/^/mozconfig: /'

    if [[ -n "$TEST_MOZILLA_HG" ]]; then
        export TEST_MOZILLA_HG_REV=${TEST_MOZILLA_HG_REV:-default}
    fi

    # js shell builds
    if [[ $buildtype == "debug" ]]; then
        unset BUILD_OPT
    else
        export BUILD_OPT=1
    fi

    case "$OSID" in
        darwin)
            export JS_EDITLINE=1 # required for mac
            ;;
    esac
    # end js shell builds

    # set default "data" variables to reduce need for data files.

    case $product in
        firefox)
            export profilename=${profilename:-$product-$branch$extra-profile}
            export profiledirectory=${profiledirectory:-/tmp/$product-$branch$extra-profile}
            export userpreferences=${userpreferences:-$TEST_DIR/prefs/test-user.js}
            export extensiondir=${extensiondir:-$TEST_DIR/xpi}
            export executablepath=${executablepath:-$BUILDTREE/mozilla/$product-$buildtype/dist}
            ;;
        js)
            export jsshellsourcepath=${jsshellsourcepath:-$BUILDTREE/mozilla/js/src}
            ;;
    esac

    if [[ -n "$datafiles" && ! -e $datafiles ]]; then
        # if there is not already a data file for this configuration, create it
        # this will save this configuration for the tester.sh and other scripts
        # which use datafiles for passing configuration values.

        echo product=\${product:-$product}                                          >> $datafiles
        echo branch=\${branch:-$branch}                                             >> $datafiles
        echo buildtype=\${buildtype:-$buildtype}                                    >> $datafiles
        if [[ $product == "js" ]]; then
            echo jsshellsourcepath=\${jsshellsourcepath:-$jsshellsourcepath}        >> $datafiles
        else
            echo profilename=\${profilename:-$profilename}                          >> $datafiles
            echo profiledirectory=\${profiledirectory:-$profiledirectory}           >> $datafiles
            echo executablepath=\${executablepath:-$executablepath}                 >> $datafiles
            echo userpreferences=\${userpreferences:-$userpreferences}              >> $datafiles
            echo extensiondir=\${extensiondir:-$extensiondir}                       >> $datafiles
        fi
        if [[ -n "$TEST_MOZILLA_HG" ]]; then
            echo TEST_MOZILLA_HG=\${TEST_MOZILLA_HG:-$TEST_MOZILLA_HG}              >> $datafiles
            echo TEST_MOZILLA_HG_REV=\${TEST_MOZILLA_HG_REV:-$TEST_MOZILLA_HG_REV}  >> $datafiles
        fi
    fi

    if [[ -n "$commands" ]]; then
        case $OSID in
            nt)
                if  ! cmd /c `cygpath -w $cmdbat` "cd $BUILDTREE/mozilla; $commands" 2>&1; then
                    error "executing commands: $commands"
                fi
                ;;
            *)
                if  ! bash -c "cd $BUILDTREE/mozilla; $commands" 2>&1; then
                    error "executing commands: $commands"
                fi
                ;;
        esac
    fi

done
