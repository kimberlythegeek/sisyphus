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
export MSVC11KEY="$MSVCROOTKEY/11.0/Setup/VC"

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

if [[ -z "$VC11DIR" ]]; then
    export VC11DIR=`regtool get "$MSVC11KEY/ProductDir" 2> /dev/null`
fi

# Determine if user has overridden the default choice of compiler
USE_MSVC_VER=$(grep USE_MSVC_VER $MOZCONFIG|sed 's|USE_MSVC_VER=\(.*\)|\1|')

if [[ -z "$USE_MSVC_VER" ]]; then

    # The official compiler for Firefox 3.6 to Firefox 13 is VC 8.
    # The official compiler for Firefox 14 and later is VC 10.

    if [[ -n "$VC11DIR" ]]; then
        USE_MSVC_VER=11
    elif [[ -n "$VC10DIR" ]]; then
        USE_MSVC_VER=10
    elif [[ -n "$VC8DIR" ]]; then
        USE_MSVC_VER=8
    elif [[ -n "$VC9DIR" || -n "$VC9EXPRESSDIR" ]]; then
        USE_MSVC_VER=9
    elif [[ -n "$VC8EXPRESSDIR" ]]; then
        USE_MSVC_VER=8
    elif [[ -n "$VC71DIR" ]]; then
        USE_MSVC_VER=71
    else
        error "Unsupported compiler version"
    fi
fi

case "$TEST_PROCESSORTYPE" in
    *32)
        startbat=start-msvc${USE_MSVC_VER}.bat
        ;;
    *64)
        startbat=start-msvc${USE_MSVC_VER}-x64.bat
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
