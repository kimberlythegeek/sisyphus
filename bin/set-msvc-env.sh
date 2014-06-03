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

if [[ -z "$VC10DIR" ]]; then
    export VC10DIR=`regtool get "$MSVC10KEY/ProductDir" 2> /dev/null`
fi

if [[ -z "$VC11DIR" ]]; then
    export VC11DIR=`regtool get "$MSVC11KEY/ProductDir" 2> /dev/null`
fi

if [[ -z "$VC12DIR" ]]; then
    export VC12DIR=`regtool get "$MSVC12KEY/ProductDir" 2> /dev/null`
fi

# Determine if user has overridden the default choice of compiler
USE_MSVC_VER=$(grep USE_MSVC_VER $MOZCONFIG|sed 's|USE_MSVC_VER=\(.*\)|\1|')

if [[ -z "$USE_MSVC_VER" ]]; then

    # The official compiler for Firefox 14 and later is VC 10.

    if [[ -n "$VC12DIR" ]]; then
        USE_MSVC_VER=2013
    elif [[ -n "$VC11DIR" ]]; then
        USE_MSVC_VER=2012
    elif [[ -n "$VC10DIR" ]]; then
        USE_MSVC_VER=2010
    else
        error "Unsupported compiler version"
    fi
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
sed 's|\(^cd.*USERPROFILE.*\)|rem \1|; s|^start /d.*|cmd /c %MOZILLABUILD%\\msys\\bin\\bash --login -i -c %1|; s|^"%MOZILLABUILD%\\msys\\bin\\bash" --login -i|cmd /c %MOZILLABUILD%\\msys\\bin\\bash --login -i -c %1|' $startbat > $cmdbat
