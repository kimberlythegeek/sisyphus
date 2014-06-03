# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

""" bisect_builds.py - perform a bisection test on nightly builds.

"""

from optparse import OptionParser
import os
import datetime
import sys
import subprocess
import re
import platform
import httplib2
import BeautifulSoup
try:
    import json
except:
    import simplejson as json

sisyphus_dir     = os.environ["TEST_DIR"]
tempdir          = os.path.join(sisyphus_dir, "bin")
if tempdir not in sys.path:
    sys.path.append(tempdir)

import build_database

def parse_datetime(s):
    """convert a string of format CCYY-MM-DD or CCYY-MM-DD-HH-MM-SS
    into a datetime object."""

    re_datetime = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
    match       = re_datetime.match(s)
    if match:
        date = datetime.datetime(int(match.group(1)),
                                 int(match.group(2)),
                                 int(match.group(3)))
    else:
        re_datetime = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(-(\d{1,2})-(\d{1,2})-(\d{1,2}))?")
        match       = re_datetime.match(s)
        if not match:
            raise Exception("Bad Date: " + s)
        date = datetime.datetime(int(match.group(1)),
                                 int(match.group(2)),
                                 int(match.group(3)),
                                 int(match.group(5)),
                                 int(match.group(6)),
                                 int(match.group(7)))
    return date


def cmp_builds(x,y):
    if x["buildid"] < y["buildid"]:
        return -1
    if x["buildid"] > y["buildid"]:
        return +1
    return 0

def download_build(url, filepath, timeout=1800):
    # download.sh -u downloadurl -f filepath -t timeout
    args = [
        sisyphus_dir + "/bin/download.sh",
        "-u", url,
        "-f", filepath,
        "-t", str(timeout)
        ]
    try:
        subprocess.check_output(args, stderr=subprocess.STDOUT)
    except AttributeError:
        proc = subprocess.Popen(args, preexec_fn=lambda : os.setpgid(0,0), # process = process group
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                close_fds=True)
        stdout = proc.communicate()[0]
        if proc.returncode != 0:
            print "download.sh: %d: %s, %s: %s" % (proc.returncode, url, filepath, stdout)
            raise Exception("download_build")

    except subprocess.CalledProcessError, e:
        print "download.sh: %d: %s, %s, %d: %s" % (e.returncode, url, filepath, timeout, e.output)
        raise

def install_build(branch, executablepath, filepath):
    # install_build.sh -p firefox -b branch -x executablepath -f filepath
    args = [
        sisyphus_dir + "/bin/install-build.sh",
        "-p", "firefox",
        "-b", branch,
        "-x", executablepath,
        "-f", filepath
        ]
    try:
        subprocess.check_output(args, stderr=subprocess.STDOUT)
    except AttributeError:
        proc = subprocess.Popen(args, preexec_fn=lambda : os.setpgid(0,0), # process = process group
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                close_fds=True)
        stdout = proc.communicate()[0]
        if proc.returncode != 0:
            print "install_build.sh: %d: %s, %s, %s: %s" % (proc.returncode, branch, executablepath, filepath, stdout)
            raise Exception("install_build")

    except subprocess.CalledProcessError, e:
        print "install_build.sh: %d: %s, %s, %s: %s" % (e.returncode, branch, executablepath, filepath, e.output)
        raise

def test_build(url, branch, test_path, timeout=1800):
    filepath = "/tmp/" + os.path.basename(url)
    executablepath = "/tmp/firefox-" + branch

    download_build(url, filepath, timeout)
    try:
        install_build(branch, executablepath, filepath)
    except:
        return 125

    returncode = subprocess.call([test_path])
    return returncode

def bisect(bisection_array, lower_index, upper_index, regression, branch, test_path):

    returncode = None

    while lower_index < upper_index:
        mid_index = (lower_index + upper_index)/2
        url = bisection_array[mid_index]["buildurl"]

        print "Testing %s" % url
        returncode = test_build(url, branch, test_path)

        if returncode == 125: # skip
            del bisection_array[mid_index]
            upper_index -= 1

        if returncode == 0:
            # test passed
            print "%s passed with returncode %d" % (url, returncode)
            if regression:
                # we are looking for transition passed to failed
                lower_index = mid_index + 1
            else:
                # we are looking for the transition failed to passed
                upper_index = mid_index - 1
        else:
            # test failed
            print "%s failed with returncode %d" % (url, returncode)
            if regression:
                # we are looking for transition passed to failed
                upper_index = mid_index - 1
            else:
                # we are looking for the transition failed to passed
                lower_index = mid_index + 1

    if returncode is None or returncode == 125:
        return None

    if regression:
        # looking for transition from passed to failed.
        if returncode == 0:
            # most recent test passed, the regression should be the next build
            index = mid_index + 1
        else:
            # most recent test failed, this should be the regression
            index = mid_index
    else:
        # looking for transition from failed to passed
        if returncode == 0:
            # most recent test passed, the fix should be this build.
            index = mid_index
        else:
            # most recent test failed, the fix should be the next build
            index = mid_index + 1

    return index


def bisect_builds(options):

    platform_data = build_database.PlatformData(options)
    database = build_database.build_database(options)

    if options.branch == "beta":
        repo = r"mozilla-beta"
    elif options.branch == r"aurora":
        repo = r"mozilla-aurora"
    elif options.branch == "nightly":
        repo = r"mozilla-central"
    elif options.branch == "inbound":
        repo = r"mozilla-inbound"
    else:
        raise Exception("Invalid branch: " + branch)

    pattern = repo
    if options.build_type == "debug":
        pattern += r"-debug"
    pattern += r"/.*\."
    if options.build_type == "debug":
        pattern += r"debug-"
    pattern += platform_data.platform + platform_data.cpu_name + r"\." + platform_data.suffix

    re_build = re.compile(pattern)
    bisection_array = []

    for build_url in database["builds"]:
        if re_build.search(build_url):
            bisection_array.append({
                "buildid": database["builds"][build_url]["buildid"],
                "changeset": database["builds"][build_url]["changeset"],
                "buildurl": build_url
            })

    database = None

    bisection_array.sort(cmp_builds)

    upper_index = len(bisection_array) - 1
    if options.buildid:
        while options.buildid < bisection_array[upper_index]['buildid']:
            upper_index -= 1

    # If the most recent build fails the test, then we are looking for the transition
    # from passed to failed, i.e. a regression.
    while True:
        url = bisection_array[upper_index]["buildurl"]
        print "Checking upper limit %s" % url
        returncode = test_build(url, options.branch, options.test_path)
        print "%s returned %d" % (url, returncode)
        if returncode != 125:
            break
        print "Skipping %s" % url
        upper_index -= 1
        if upper_index < 0:
            print "Skipped all builds. Terminating."
            exit(1)

    regression = (returncode != 0)
    if regression:
        tag = "regression"
    else:
        tag = "fix"

    # Now we want to find an earlier build that has the opposite
    # success factor. We don't want to go back too far in time so that
    # we don't get confused by multiple transitions passed -> failed
    # -> passed -> failed ->... We start out going back 1/2 of the
    # train schedule 42/2 = 21 days then increase the jump by 21 days
    # each time we do not find the starting point. Hopefully this
    # won't skip over a passed-failed boundary but will not take too
    # long to find the beginning changeset.

    build_window = options.build_window
    while True:
        build_window += options.build_window_increment
        lower_index = upper_index - build_window
        if lower_index < 0:
            lower_index = 0

        while True:
            url = bisection_array[lower_index]["buildurl"]
            print "Checking lower limit %s" % url
            returncode = test_build(url, options.branch, options.test_path)
            print "%s returned %d" % (url, returncode)
            if returncode != 125:
                break
            print "Skipping %s" % url
            lower_index -= 1
            if lower_index < 0:
                print "Could not find lower limit. Terminating"
                exit(1)

        failed = (returncode != 0)

        if (regression and not failed) or (not regression and failed):
            # for regressions we are looking for the transition from passed to failed
            # while for fixes we are looking for the transition from failed to passed.
            break

        if regression and failed or not regression and not failed:
            # the test transition occurred before lower_index
            upper_index = lower_index
            if lower_index == 0:
                # We did not find a transition and can not search for it. :-(
                if regression:
                    print "searching for regression: could not find build where test passed"
                else:
                    print "searching for fix: could not find build where test failed"
                exit(1)

    build_index = bisect(bisection_array, lower_index, upper_index, regression, options.branch, options.test_path)
    if not build_index:
        print ("Could not find %s between %s, %s, %s and %s, %s, %s" %
               (tag,
                bisection_array[lower_index]["buildid"],
                bisection_array[lower_index]["changeset"],
                bisection_array[lower_index]["buildurl"],
                bisection_array[upper_index]["buildid"],
                bisection_array[upper_index]["changeset"],
                bisection_array[upper_index]["buildurl"]))
    else:
        build = bisection_array[build_index]
        prev_build_index = build_index - 1
        if prev_build_index < 0:
            prev_build_index = 0
        prev_build = bisection_array[prev_build_index]
        reChangeset = re.compile("https://hg.mozilla.org/(.*)/rev/(.*)")
        match = reChangeset.match(prev_build["changeset"])
        repo = match.group(1)
        fromchangeset = match.group(2)
        match = reChangeset.match(build["changeset"])
        tochangeset = match.group(2)
        pushlog = "https://hg.mozilla.org/%s/pushloghtml?fromchange=%s&tochange=%s" % (repo, fromchangeset, tochangeset)

        print "Found %s between %s-%s" % (tag, prev_build["buildid"], build["buildid"])
        print "Pushlog: %s" % pushlog
        print prev_build["buildurl"]
        print build["buildurl"]

if __name__ == "__main__":
    usage = """usage: %prog [options]"""

    parser = OptionParser(usage=usage)

    parser.add_option("--database-start-date", action="store",
                      dest="database_start_date",
                      help="Database starting date. Defaults to 2011-04-01",
                      default="2011-04-01")

    parser.add_option("--branch", action="store",
                      dest="branch",
                      help="Branch to test: beta, aurora, nightly, inbound. Defaults to nighlty.",
                      default="nightly")

    parser.add_option("--build-type", action="store",
                      dest="build_type",
                      help="build type: one of opt, debug. Defaults to debug",
                      default="debug")

    parser.add_option("--processor-type", action="store", type="string",
                       dest="processor_type",
                       help="Override default processor type: intel32, intel64, amd32, amd64",
                       default=None)

    parser.add_option("--test-path", action="store", type="string",
                       dest="test_path",
                       help="Path to test script.",
                       default=None)

    parser.add_option("--buildid", action="store", type="string",
                       dest="buildid",
                       help="Maximum BuildID (CCYYMMDDHHSS) of first build to test. Defaults to latest.",
                       default=None)

    parser.add_option("--build-window", action="store", type="int",
                       dest="build_window",
                       help="Number of days in initial build window during search. Defaults to 21 days.",
                       default=7)

    parser.add_option("--build-window-increment", action="store", type="int",
                       dest="build_window_increment",
                       help="Number of days to increase build window date increment during search. Defaults to 0 days.",
                       default=0)

    (options, args) = parser.parse_args()

    if options.test_path is None:
        raise Exception("test-path")

    bisect_builds(options)
