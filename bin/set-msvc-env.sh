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
export MSVC10KEY="$MSVCROOTKEY/10.0/Setup/VC"
export MSVC11KEY="$MSVCROOTKEY/11.0/Setup/VC"
export MSVC12KEY="$MSVCROOTKEY/12.0/Setup/VC"
export MSVC14KEY="$MSVCROOTKEY/14.0/Setup/VC"

if [[ -z "$VC10DIR" ]]; then
    export VC10DIR=`regtool get "$MSVC10KEY/ProductDir" 2> /dev/null`
fi

if [[ -z "$VC11DIR" ]]; then
    export VC11DIR=`regtool get "$MSVC11KEY/ProductDir" 2> /dev/null`
fi

if [[ -z "$VC12DIR" ]]; then
    export VC12DIR=`regtool get "$MSVC12KEY/ProductDir" 2> /dev/null`
fi

if [[ -z "$VC14DIR" ]]; then
    export VC14DIR=`regtool get "$MSVC14KEY/ProductDir" 2> /dev/null`
fi

# The official compiler for Firefox 14 and later is VC 10.
# Determine if user has overridden the default choice of compiler
USE_MSVC_VER=$(grep USE_MSVC_VER $MOZCONFIG|sed 's|USE_MSVC_VER=\(.*\)|\1|')

if [[ -z "$USE_MSVC_VER" ]]; then

    if [[ -n "$VC14DIR" ]]; then
        USE_MSVC_VER=2015
    elif [[ -n "$VC12DIR" ]]; then
        USE_MSVC_VER=2013
    elif [[ -n "$VC11DIR" ]]; then
        USE_MSVC_VER=2012
    elif [[ -n "$VC10DIR" ]]; then
        USE_MSVC_VER=2010
    else
        echo "WARNING: compiler version not detected"
    fi
fi

if [[ -n "$USE_MSVC_VER" ]]; then
    # mozilla-build 2.2 and later changed the organization of the
    # start*.bat files. If we have USE_MSVC_VER defined for 2010 or
    # 2012 assume we are using an older version of mozilla build
    # located in $mozillabuild.old
    new_mozilla_build=1
    if [[ "$USE_MSVC_VER" -lt "2013" ]]; then
        new_mozilla_build=0
        mozillabuild=${mozillabuild}.old
    fi

    case "$TEST_PROCESSORTYPE" in
        *32)
            startbat=start-shell-msvc${USE_MSVC_VER}.bat
            ;;
        *64)
            startbat=start-shell-msvc${USE_MSVC_VER}-x64.bat
            ;;
    esac

    # set VCINSTALLDIR for use in detecting the MS CRT
    # source when building jemalloc.
    # see Advanced Scripting Guide Indirect References
    # http://tldp.org/LDP/abs/html/ivr.html
    eval VCINSTALLDIR=\$VC${USE_MSVC_VER}DIR

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
    if [[ "$new_mozilla_build" == "0" ]]; then
        sed 's|\(^cd.*USERPROFILE.*\)|rem \1|; s|^start /d.*|cmd /c %MOZILLABUILD%\\msys\\bin\\bash --login -i -c %1|; s|^"%MOZILLABUILD%\\msys\\bin\\bash" --login -i|cmd /c %MOZILLABUILD%\\msys\\bin\\bash --login -i -c %1|' $startbat > $cmdbat
    else
        startshellbat=$mozillabuild/start-shell.bat
        msysshellbat=$mozillabuild/msys-command-shell.bat
        sed 's|CALL start-shell.bat|CALL msys-command-shell.bat %1|' $startbat > $cmdbat
        sed 's|\(^cd.*USERPROFILE.*\)|rem \1|; s|^PAUSE|rem PAUSE|; s|%MOZILLABUILD%msys\\bin\\bash --login -i|cmd /c %MOZILLABUILD%\msys\\bin\\bash --login -i -c %1|' $startshellbat > $msysshellbat
    fi

fi
