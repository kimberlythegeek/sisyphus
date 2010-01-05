#!/bin/bash 

if [[ -z "$TEST_DIR" ]]; then
  cat <<EOF
`basename $0`: error

TEST_DIR, the location of the Sisyphus framework, 
is required to be set prior to calling this script.
EOF
  exit 2
fi

if [[ ! -e $TEST_DIR/bin/library.sh ]]; then
    echo "TEST_DIR=$TEST_DIR"
    echo ""
    echo "This script requires the Sisyphus testing framework. Please "
    echo "cvs check out the Sisyphys framework from mozilla/testing/sisyphus"
    echo "and set the environment variable TEST_DIR to the directory where it"
    echo "located."
    echo ""

    exit 2
fi

source $TEST_DIR/bin/library.sh

#TEST_TOPSITE_TIMEOUT=${TEST_TOPSITE_TIMEOUT:-14400}
#TEST_TOPSITE_PAGE_TIMEOUT=${TEST_TOPSITE_PAGE_TIMEOUT:-1800}

TEST_TOPSITE_TIMEOUT=${TEST_TOPSITE_TIMEOUT:-3600}
TEST_TOPSITE_PAGE_TIMEOUT=${TEST_TOPSITE_PAGE_TIMEOUT:-120}

#
# options processing
#
options="p:b:x:N:s:u:D:d:h:rH"
function usage()
{
    cat <<EOF
usage: 
$SCRIPT -p product  -b branch -x executablepath -N profilename 
        [-s sitelist|-u url] -D depth -r [-d datafiles]

variable            description
===============     ============================================================
-p product          required. product [firefox|thunderbird|fennec]
-b branch           required. one of 1.8.0, 1.8.1, 1.9.0
-x executablepath   required. directory tree containing executable
-N profilename      required. name of profile
-s sitelist         optional. text file with a url per line to be spidered.
-u url              optional. url to be spidered.

                    only one of sitelist or url may be specified at the
                    same time.

-D depth            optional. depth to spider each listed url
-h userhook         optional. url to user hook script.
-r                  optional. obey robots.txt
-H                  optional. report http responses.
-d datafiles        optional. one or more filenames of files containing
                    environment variable definitions to be included.

                    note that the environment variables should have the same
                    names as in the "variable" column.

if an argument contains more than one value, it must be quoted.
EOF
    exit 2
}

unset product branch executablepath profilename sitelist depth robots

while getopts $options optname ;
do
    case $optname in
	p) product=$OPTARG;;
	b) branch=$OPTARG;;
	x) executablepath=$OPTARG;;
	N) profilename=$OPTARG;;
	s) sitelist=$OPTARG;;
	u) url=$OPTARG;;
	D) depth="-depth $OPTARG";;
	r) robots="-robot";;
	H) httpresponses="-httpresponses";;
        d) datafiles=$OPTARG;;
        h) hook=$OPTARG;;
    esac
done

# include environment variables
if [[ -n "$datafiles" ]]; then
    for datafile in $datafiles; do
        source $datafile
    done
fi

if [[ -z "$product" || -z "$branch" || -z "$executablepath" || -z "$profilename" ]]; then
    usage
fi

if [[ -z "$url" && -z "$sitelist" || -n "$url" && -n "$sitelist"  ]]; then
    usage
fi

hook=${hook:-"http://$TEST_HTTP/tests/mozilla.org/top-sites/userhook.js"}

executable=`get_executable $product $branch $executablepath`

if [[ -n "$url" ]]; then
    timed_run.py $TEST_TOPSITE_TIMEOUT "$url" \
        $EXECUTABLE_DRIVER \
	"$executable" -spider -P "$profilename" \
	-uri "$url" \
	-hook "$hook" \
	-timeout $TEST_TOPSITE_PAGE_TIMEOUT \
	-start -quit $robots $httpresponses $depth \
	-jserrors

    if [[ "$?" == "99" ]]; then
	error "User Interrupt" $LINENO
    fi
elif [[ -n "$sitelist" ]]; then
    if [[ ! -e "$sitelist" ]]; then
        error "sitelist $sitelist does not exist" $LINENO
    else
        cat $sitelist | while read url; do
            timed_run.py $TEST_TOPSITE_TIMEOUT "$url" \
                $EXECUTABLE_DRIVER \
	        "$executable" -spider -P "$profilename" \
	        -uri "$url" \
	        -hook "$hook" \
	        -timeout $TEST_TOPSITE_PAGE_TIMEOUT \
	        -start -quit $robots $httpresponses $depth \
	        -jserrors

            if [[ "$?" == "99" ]]; then
	        error "User Interrupt" $LINENO
            fi
        done
    fi
fi
