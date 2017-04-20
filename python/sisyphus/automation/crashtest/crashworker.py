# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import re
import signal
import subprocess
import sys
import time

from optparse import OptionParser

sisyphus_dir     = os.environ["SISYPHUS_DIR"]
tempdir          = os.path.join(sisyphus_dir, 'python')
if tempdir not in sys.path:
    sys.path.append(tempdir)

tempdir          = os.path.join(tempdir, 'sisyphus')
if tempdir not in sys.path:
    sys.path.append(tempdir)

tempdir          = os.path.join(tempdir, 'webapp')
if tempdir not in sys.path:
    sys.path.append(tempdir)

os.environ['DJANGO_SETTINGS_MODULE'] = 'sisyphus.webapp.settings'

import django
django.setup()

from django.db import connection
import sisyphus.webapp.settings
sisyphus_url      = os.environ["SISYPHUS_URL"]
post_files_url    = sisyphus_url + '/post_files/'

from sisyphus.webapp.bughunter import models
from sisyphus.automation import utils, worker, program_info

os.environ["MOZ_CRASHREPORTER"]="1"
os.environ["MOZ_CRASHREPORTER_NO_REPORT"]="1"
os.environ["MOZ_KEEP_ALL_FLASH_MINIDUMPS"]="1"
os.environ["XPCOM_DEBUG_BREAK"]="stack"
os.environ["RUST_BACKTRACE"]="1"
os.environ["userpreferences"]= sisyphus_dir + '/prefs/spider-user.js'

class CrashTestWorker(worker.Worker):

    def __init__(self, options):
        worker.Worker.__init__(self, "crashtest", options)

        self.model_test_run       = models.SiteTestRun
        self.model_test_assertion = models.SiteTestAssertion
        self.model_test_crash     = models.SiteTestCrash
        self.model_test_valgrind  = models.SiteTestValgrind
        self.model_test_crash_dump_meta_data = models.SiteTestCrashDumpMetaData

        self.testrun_row = None
        self.save()

        # Workers obtain signatures to process by retrieving them from
        # the pending jobs view.

        # Priorities are used to order groups of jobs. Jobs are
        # processed in the order of their priorities: 0, 1, 2, and 3.

        # Priority 0 is reserved for jobs which are created from urls
        # that have generated crashes. A Priority 0 job is created
        # from a crashing url for each worker class (operating system,
        # operating system version and cpu type). We wish to check
        # these urls quickly to determine if a crash is reproducible.

        # Priority 1 is reserved for jobs which have been uploaded via
        # crashurlloader.py. A Priority 1 job is created from each
        # input url for each worker class (operating system, operating
        # system version and cpu type) containing a single crashing
        # url.

        # Priority 2 is reserved.

        # Priority 3 is reserved for jobs uploaded via crashparser.py.

        # Priority 0 and Priority 1 jobs are created in such a way to
        # guarantee that they cover each possible combination of
        # operating system, operating system version and cpu type.
        # Therefore workers perform exact matches on operating system,
        # operating system version and cpu type for Priority 0 and
        # Priority 1 jobs. This prevents partially matching workers from
        # opportunistically testing the same Priority 0 or Priority 1
        # url multiple times.


        # self.userhook is the url of the userhook script to be executed
        # for each page load.
        self.userhook = sisyphus.webapp.settings.SISYPHUS_URL + '/media/userhooks/' + options.userhook

        self.page_timeout = options.page_timeout
        self.site_timeout = options.site_timeout

        # self.invisible is the optional argument to the top-sites.sh test script
        # to make Spider hide the content being loaded.
        if options.invisible:
            self.invisible = ' -i '
        else:
            self.invisible = ''

        # string containing a space delimited list of paths to third-party symbols
        # for use by minidump_stackwalk
        self.symbols_paths = options.symbols_paths.split(' ')

        # Use a property to record whether the test process has been hung in order
        # to allow the hung alarm signal to set its value.
        self.hung_process = False

        self.do_not_reproduce_bogus_signatures = options.do_not_reproduce_bogus_signatures

    def runTest(self, extra_test_args):

        self.debugMessage("testing firefox %s %s %s" % (self.branch, self.buildtype, self.testrun_row.socorro.url))
        self.hung_process = False
        self.state        = "testing"
        self.save()

        # kill any test processes still running.
        test_process_dict = self.psTest()
        if test_process_dict:
            self.logMessage('runTest: test processes running before test')
            self.killTest()

        socorro_row = self.testrun_row.socorro

        try:
            url = utils.encodeUrl(socorro_row.url)
        except Exception, e:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('runTest: exception: %s, %s: url: %s' % (exceptionValue, errorMessage, url))
            self.testrun_row.state = 'completed'
            self.state             = 'completed'
            self.testrun_row.save()
            self.testrun_row  = None
            self.save()
            return

        self.testrun_row.changeset = self.build_row.changeset
        self.testrun_row.extra_test_args = extra_test_args
        self.testrun_row.save()

        page               = "startup"
        executablepath     = ""
        profilename        = ""
        page_http_403      = False # page returned 403 Forbidden
        reFatalError       = re.compile(r'FATAL ERROR')
        reExecutablePath   = re.compile(r'^environment: TEST_EXECUTABLEPATH=(.*)')
        reProfileName      = re.compile(r'^environment: TEST_PROFILENAME=(.*)')
        reAssertionFail    = re.compile(r'(Assertion failure: .*), at .*')
        reMOZ_CRASH        = re.compile(r'(Hit MOZ_CRASH[(][^)]*[)]) at .*')
        reABORT            = re.compile(r'###\!\!\! (ABORT: .*)')
        reABORT2           = re.compile(r'###\!\!\! (ABORT: .*), file (.*), line [0-9]+.*')
        reABORT3           = re.compile(r'###\!\!\! (ABORT: .*) file (.*), line [0-9]+.*')
        reASSERTION        = re.compile(r'###\!\!\! ASSERTION: (.*), file (.*), line [0-9]+.*')
        reValgrindLeader   = re.compile(r'^==[0-9]+==')
        reSpiderBegin      = re.compile(r'^Spider: Begin loading (.*)')
        reSpider           = re.compile(r'^Spider:')
        reUrlExitStatus    = re.compile(r'^(http.*): EXIT STATUS: (.*) [(].*[)].*')
        # AddressSanitizer patterns
        # reAsanStart pid - group 1, message - group 2
        reAsanStart        = re.compile(r'^==(\d+)==ERROR: (AddressSanitizer: .*)')
        # reAsanEnd pid - group 1 must match, reason - group 2
        reAsanEnd          = re.compile(r'^==(\d+)==(.*)')
        # reAsanFrame frame number - group 1, address - group 2, funcdecl - group 3
        reAsanFrame        = re.compile(r'^ {4}(#\d+) (0x[0-9a-fA-F]+) in (.*) [^ ]+$')
        reAsanThread       = re.compile(r'Thread.*created by.*here:')
        # rAsanSummary - reason - group 1
        reAsanSummary      = re.compile(r'SUMMARY: AddressSanitizer: ([^ ]*)')
        reAsan             = re.compile(r'AddressSanitizer')
        reAsanBlank        = re.compile(r' *$')

        # Spider: HTTP Response: originalURI: http://bclary.com/build/style URI: http://bclary.com/build/style referer: http://bclary.com/ status: 200 status text: ok content-type: text/css succeeded: true
        reHTTP    = re.compile(r'^Spider: HTTP Response: originalURI:')
        reHTTP403 = re.compile(r'^Spider: HTTP Response: originalURI: (.*) URI: (.*) referer: (.*) status: 403 status text: (.*) content-type: (.*) succeeded: (.*)')

        environment = dict(os.environ)

        # set up environment.
        if self.os_name == "Mac OS X":
            # Set up debug malloc error handling for Mac OS X.
            # http://developer.apple.com/mac/library/releasenotes/DeveloperTools/RN-MallocOptions/index.html#//apple_ref/doc/uid/TP40001026-DontLinkElementID_1
            # XXX: kludge.
            # we want to enable malloc scribble on Mac OS X, but don't want it
            # active for the shell scripts and other commands used to run the
            # tests as the extra output from the command line tools breaks the
            # scripts. Set an environment variable that can be checked by the
            # test script in order to turn on malloc scribble on Mac OS X.
            environment["EnableMallocScribble"] = "1"

        # buffers to hold assertions and valgrind messages until
        # a test result is seen in the output.
        assertion_dict = {}
        valgrind_text  = ""
        # There may be an Asan message for each process.
        asan_list = []

        # attempt to silence undefined errors if exception thrown during communicate.
        stdout = ''

        fatal_error = False
        buildspec = self.parse_buildspec(self.buildtype)
        if buildspec['extra']:
            branch = '%s-%s' % (self.branch, buildspec['extra'])
        else:
            branch = self.branch
        args = [
            "./bin/tester.sh",
            "-t",
            "tests/mozilla.org/top-sites/test.sh -u " +
            url +
            self.invisible + " -H -D 1 -h " + self.userhook,
            self.product,
            branch,
            buildspec['buildtype'],
        ]

        self.debugMessage('Running test: %s' % args)

        proc = subprocess.Popen(
            args,
            preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True,
            env=environment)

        try:
            # When a stuck plugin-container process or other process
            # spawned by the test is not killed by the normal time out
            # procedure, we need to kill the process ourselves. Fire
            # the time out alarm 30 seconds after the test should have
            # timed out.
            def timeout_handler(signum, frame):
                self.logMessage("runTest: %s timed out" % url)
                self.hung_process = True
                self.killTest(proc.pid)

            default_alarm_handler = signal.getsignal(signal.SIGALRM)
            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.site_timeout + 30)
                stdout = proc.communicate()[0]
            except OSError, oserror:
                if oserror.errno != 10:
                    raise
                # Ignore OSError 10: No child process
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, default_alarm_handler)

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception, e:

            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('runTest: %s, exception: %s, %s' % (url, exceptionValue, errorMessage))

            if exceptionType == OSError:
                if (e.errno == 12 or
                    e.errno == 23 or
                    e.errno == 24):
                    # Either out of memory or too many open files. We
                    # can not reliably recover so just reload the
                    # program and start over.
                    try:
                        self.logMessage('runTest: %s, OSError.errno=%d. Restarting.' %
                                        (url, e.errno))
                    except:
                        # Just ignore the error if we can't log the problem.
                        pass
                    try:
                        self.reloadProgram()
                    except:
                        # Exit if we can't restart the program.
                        sys.exit(2)

            elif exceptionType == ValueError:
                if errorMessage.find('filedescriptor out of range') != -1:
                    self.logMessage('runTest: %s, filedescriptors %d out of range. Restarting.' %
                                    (url, utils.openFileDescriptorCount()))
                    # Closing file descriptors and trying again does not
                    # fix the issue on Windows. Just restart the program.
                    try:
                        self.reloadProgram()
                    except:
                        # Exit if we can't restart the program.
                        sys.exit(2)

        match = re.search('log: (.*\.log) ', stdout)
        if match:
            logfilename = match.group(1)

            logfile = open(logfilename, "r")

            while 1:
                line = logfile.readline()
                if not line:
                    break

                # decode to unicode
                line = utils.makeUnicodeString(line)

                match = reAsanStart.match(line)
                if match:
                    asan_list.append({
                        'pid': match.group(1),
                        'error': match.group(2),
                        'text': line,
                        'frames': [],
                        'reason': '',
                        'frames_collected': False,
                        'completed': False,
                        })
                    self.testrun_row.fatal_message = match.group(2)
                    continue
                if asan_list and not asan_list[-1]['completed']:
                    match = reAsanFrame.match(line)
                    if match:
                        asan_list[-1]['text'] += line
                        if not asan_list[-1]['frames_collected']:
                            asan_list[-1]['frames'].append(match.group(3))
                        continue
                    match = reAsanBlank.match(line)
                    if match:
                        asan_list[-1]['text'] += line
                    match = reAsan.match(line)
                    if match:
                        asan_list[-1]['text'] += line
                        continue
                    match = reAsanThread.match(line)
                    if match:
                        asan_list[-1]['text'] += line
                        continue
                    match = reAsanSummary.match(line)
                    if match:
                        asan_list[-1]['text'] += line
                        asan_list[-1]['reason'] = match.group(1)
                        asan_list[-1]['frames_collected'] = True
                        continue
                    if not asan_list[-1]['reason']:
                        # ignore lines such as ==7924==WARNING: ...
                        match = reAsanEnd.match(line)
                        if match:
                            if match.group(1) != asan_list[-1]['pid']:
                                self.debugMessage('Asan pid %s mismatch %s: %s' % (
                                    match.group(1), asan_list[-1]['pid'], line))
                            asan_list[-1]['completed'] = True
                            asan_list[-1]['text'] += line

                match = reFatalError.match(line)
                if match:
                    fatal_error = True
                    self.logMessage("runTest: %s: %s" % (url, line))

                if not executablepath:
                    match = reExecutablePath.match(line)
                    if match:
                        executablepath = match.group(1)
                        continue

                if not profilename:
                    match = reProfileName.match(line)
                    if match:
                        profilename = match.group(1)
                        continue

                # record the steps Spider took
                match = reSpider.match(line)
                if match:
                    # Exclude the HTTP responses as they are too big.
                    match = reHTTP.match(line)
                    if not match:
                        self.testrun_row.steps += line

                # Dump assertions and valgrind messages whenever we see a
                # new page being loaded.
                match = reSpiderBegin.match(line)
                if match:
                    self.process_assertions(assertion_dict, page, "crashtest", extra_test_args)
                    valgrind_list = self.parse_valgrind(valgrind_text)
                    self.process_valgrind(valgrind_list, page, "crashtest", extra_test_args)

                    assertion_dict   = {}
                    valgrind_text    = ""
                    valgrind_list    = None
                    if match:
                        page = match.group(1).strip()
                        try:
                            page = utils.encodeUrl(page)
                        except Exception, e:
                            exceptionType, exceptionValue, errorMessage = utils.formatException()
                            self.logMessage('runTest: %s, exception: %s, %s: page: %s' % (url, exceptionValue, errorMessage, page))
                            page = None
                    continue

                match = reHTTP403.match(line)
                if match:
                    page_http_403 = True
                    continue

                # Collect the first occurrence of a fatal message
                match = reAssertionFail.search(line)
                if match and not self.testrun_row.fatal_message:
                    self.testrun_row.fatal_message = match.group(1)
                    continue

                match = reMOZ_CRASH.search(line)
                if match and not self.testrun_row.fatal_message:
                    self.testrun_row.fatal_message = match.group(1)
                    continue

                match = reABORT.search(line)
                if match and not self.testrun_row.fatal_message:
                    self.testrun_row.fatal_message = match.group(1).rstrip()
                    match = reABORT2.search(line)
                    if match:
                        self.testrun_row.fatal_message = match.group(1)
                    match = reABORT3.search(line)
                    if match:
                        self.testrun_row.fatal_message = match.group(1)
                    continue

                match = reASSERTION.search(line)
                if match:
                    # record the assertion for later output when we know the test
                    assertionmessage = match.group(1)
                    assertionfile    = re.sub('^([a-zA-Z]:/|/[a-zA-Z]/)', '/', re.sub(r'\\', '/', match.group(2)))
                    assertionkey     = assertionmessage + ':' + assertionfile
                    if assertionkey in assertion_dict:
                        assertion_dict[assertionkey]["count"] += 1
                    else:
                        assertion_dict[assertionkey] = {
                            "message": assertionmessage,
                            "file"   : assertionfile,
                            "stack"  : "", # need to collect stack
                            "count"  : 1
                            }
                    continue

                match = reValgrindLeader.match(line)
                if match:
                    valgrind_text += line
                    continue

                match = reUrlExitStatus.match(line)
                if match:
                    self.testrun_row.exitstatus       = match.group(2)
                    if re.search('(CRASHED|ABNORMAL)', self.testrun_row.exitstatus):
                        self.testrun_row.crashed = True
                    else:
                        self.testrun_row.crashed = False

            logfile.close()

            if self.testrun_row.fatal_message:
                # remove any trailing commas or colons and convert any raw hex addresses to 0x
                # so that fatal_messages can be combined regardless of the runtime values of
                # the addresses.
                self.testrun_row.fatal_message = self.testrun_row.fatal_message.rstrip(',:')
                self.testrun_row.fatal_message = re.sub('0x[0-9a-fA-F]+', '0x', self.testrun_row.fatal_message)

            baselogfilename = os.path.basename(logfilename)
            loguploadpath = 'logs/' + baselogfilename[:16].replace('-', '/') # CCYY/MM/DD/HH/MM
            dmpuploadpath = 'minidumps/' + baselogfilename[:16].replace('-', '/') # CCYY/MM/DD/HH/MM
            uploader = utils.FileUploader(post_files_url,
                                          self.model_test_run.__name__, self.testrun_row, self.testrun_row.id,
                                          loguploadpath)
            if fatal_error:
                # Fatal error occurred in the test framework. Return the job
                # to the waiting pool and terminate. The log containing the
                # fatal error messages will remain in the worker's results directory.
                uploader.add('log', baselogfilename, logfilename, True, False)
                self.testrun_row = uploader.send()
                self.testrun_row.state = 'waiting'
                self.testrun_row.worker = None
                self.testrun_row.save()
                self.testrun_row = None
                self.save()
                raise Exception("CrashWorker.runTest.FatalError")

            uploader.add('log', baselogfilename, logfilename, True)
            self.testrun_row = uploader.send()

            self.process_asan(asan_list, page, dmpuploadpath)

            symbolsPath = os.path.join(executablepath, 'crashreporter-symbols')

            symbolsPathList = [symbolsPath]
            symbolsPathList.extend(self.symbols_paths)
            self.process_dump_files(profilename, page,
                                    symbolsPathList,
                                    dmpuploadpath)


        test_process_dict = self.psTest()
        if test_process_dict:
            self.hung_process = True
            self.logMessage('runTest: %s, test processes still running' % url)
            self.killTest(proc.pid)

        if self.hung_process:
            if self.testrun_row.exitstatus:
                self.testrun_row.exitstatus += ' HANG'
            else:
                self.testrun_row.exitstatus = 'HANG'

        self.testrun_row.save()

        reproduce_signature = True

        if self.testrun_row.crashed and self.do_not_reproduce_bogus_signatures:
            # Bogus signatures consist of a single frame surrounded by parentheses.
            # Flash 11.4+ crashes on Windows 7 64bit with 32bit builds generate a large
            # number of such crashes which are not reproducible on other systems.
            # To keep other workers from attempting to reproduce these crashes,
            # we've introduced an option to ignore them when generating crashes
            # to be reproduced.

            # We will check each crash signature reported for this url and if all
            # signatures are bogus, we will ignore it.

            self.debugMessage('Checking if this crash produced a bogus signature.')

            is_bogus_signature = True
            reBogusSignature = re.compile(r'[(][^)]+[)]$')

            testcrash_rows = models.SiteTestCrash.objects.filter(testrun = self.testrun_row.id)
            for testcrash_row in testcrash_rows:
                if reBogusSignature.match(testcrash_row.crash.signature):
                    self.debugMessage('Bogus signature: %s' % testcrash_row.crash.signature)
                else:
                    self.debugMessage('Non-Bogus signature: %s' % testcrash_row.crash.signature)
                    is_bogus_signature = False
                    break
            if is_bogus_signature:
                self.debugMessage('Skipping reproduction of crash with bogus signature.')
                reproduce_signature = False

        if (reproduce_signature and
            (self.testrun_row.crashed or asan_list) and
            self.testrun_row.priority not in '01'):

            # Generate new priority 0 jobs for the other operating systems if the job
            # was not a priority 0 or priority 1 (user submitted).

            try:
                worker_rows   = (models.Worker.objects.
                                 filter(worker_type__exact = self.worker_type).
                                 exclude(state__exact = 'disabled').
                                 exclude(state__exact = 'dead'))
                branches_rows = models.Branch.objects.all().order_by('major_version')
                # Eliminate any duplicate mappings in the Version to Branch mapping
                # By picking the row with highest major_version. The ascending sort
                # guarantees the branch row with the highest major_version will be kept.
                branches_dict = {}
                for branch_row in branches_rows:
                    branches_dict[branch_row.branch + branch_row.buildtype] = branch_row
                branches_list = []
                for branch in branches_dict:
                    branches_list.append(branches_dict[branch])

                # record each worker's os, and cpu information in a hash
                # so that we only emit one signature per combination rather
                # than one for each worker.
                os_cpu_hash = {}

                for worker_row in worker_rows:
                    # Skip other workers who match us exactly but do reissue a
                    # signature for us so that we can test if the crash is also
                    # reproducible on the same machine where it originally occured.
                    if (worker_row.hostname   != self.hostname and
                        worker_row.os_name    == self.os_name and
                        worker_row.os_version == self.os_version and
                        worker_row.cpu_name   == self.cpu_name and
                        worker_row.build_cpu_name == self.build_cpu_name and
                        worker_row.buildspecs == self.buildspecs):
                        continue

                    worker_os_cpu_key = (
                        worker_row.os_name + worker_row.os_version +
                        worker_row.cpu_name + worker_row.build_cpu_name +
                        worker_row.buildspecs)

                    if worker_os_cpu_key in os_cpu_hash:
                        # we've already emitted a signature for this os/cpu.
                        continue

                    os_cpu_hash[worker_os_cpu_key] = 1

                    if worker_row.buildspecs:
                        buildspecs = set(worker_row.buildspecs.split(','))
                    else:
                        buildspecs = set()

                    for branch_row in branches_list:
                        if branch_row.product != self.product:
                            continue

                        if buildspecs and branch_row.buildtype not in buildspecs:
                            self.debugMessage('Not generating a 0 priority job for worker '
                                              '%s %s for branch %s buildtype %s' % (
                                                  worker_row.hostname,
                                                  worker_row.buildspecs,
                                                  branch_row.branch,
                                                  branch_row.buildtype))
                            continue
                        self.debugMessage('Generating a 0 priority job for worker '
                                          '%s %s for branch %s buildtype %s' % (
                                              worker_row.hostname,
                                              worker_row.buildspecs,
                                              branch_row.branch,
                                              branch_row.buildtype))

                        # PowerPC is not supported after Firefox 3.6
                        if branch_row.major_version > '0306' and worker_row.cpu_name == 'ppc':
                            continue

                        # 64 bit builds are not fully supported for 1.9.2 on Mac OS X 10.6
                        if (branch_row.branch == "1.9.2" and
                            worker_row.os_name == "Mac OS X" and
                            worker_row.os_version == "10.6" and
                            worker_row.build_cpu_name == "x86_64"):
                            continue

                        old_test_run = self.testrun_row

                        new_socorro_row = models.SocorroRecord(
                            signature           = old_test_run.socorro.signature,
                            url                 = page,
                            uuid                = '',
                            client_crash_date   = None,
                            date_processed      = None,
                            last_crash          = None,
                            product             = self.product,
                            version             = '',
                            build               = '',
                            branch              = branch_row.branch,
                            os_name             = worker_row.os_name,
                            os_full_version     = worker_row.os_version,
                            os_version          = worker_row.os_version,
                            cpu_info            = worker_row.cpu_name,
                            cpu_name            = worker_row.cpu_name,
                            address             = '',
                            bug_list            = '',
                            user_comments       = '',
                            uptime_seconds      = None,
                            adu_count           = None,
                            topmost_filenames   = '',
                            addons_checked      = '',
                            flash_version       = '',
                            hangid              = '',
                            reason              = '',
                            process_type        = '',
                            app_notes           = '',
                            )

                        new_socorro_row.save()

                        new_test_run = models.SiteTestRun(
                            os_name           = worker_row.os_name,
                            os_version        = worker_row.os_version,
                            cpu_name          = worker_row.cpu_name,
                            product           = self.product,
                            branch            = branch_row.branch,
                            buildtype         = branch_row.buildtype,
                            build_cpu_name    = worker_row.build_cpu_name,
                            worker            = None,
                            socorro           = new_socorro_row,
                            changeset         = None,
                            major_version     = branch_row.major_version,
                            bug_list          = None,
                            crashed           = False,
                            extra_test_args   = old_test_run.extra_test_args,
                            steps             = '',
                            fatal_message     = None,
                            exitstatus        = None,
                            log               = None,
                            priority          = '0',
                            state             = 'waiting',
                            )

                        new_test_run.save()

                        self.debugMessage('runTest: adding reproducer signature document: %s' % new_test_run)

            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                self.logMessage('runTest: unable to duplicate signature %s for reproduction: %s' % (self.testrun_row, errorMessage))

        # process any remaining assertion or valgrind messages.
        self.process_assertions(assertion_dict, page, "crashtest", extra_test_args)
        valgrind_list = self.parse_valgrind(valgrind_text)
        self.process_valgrind(valgrind_list, page, "crashtest", extra_test_args)

        # A resource was forbidden. Rather than continuing to attempt
        # to load a forbidden url, remove all waiting jobs for it.
        if page_http_403:
            if not utils.getLock('sisyphus.bughunter.sitetestrun', 300):
                self.debugMessage("runTest: lock timed out attempting to remove forbidden urls")
            else:
                try:
                    cursor = connection.cursor()
                    cursor.execute("""DELETE SiteTestRun FROM SocorroRecord, SiteTestRun WHERE
                                   SiteTestRun.socorro_id = SocorroRecord.id AND
                                   SiteTestRun.state = 'waiting' AND
                                   SocorroRecord.url = %s""",
                                   [url])
                except:
                    raise
                finally:
                    lockDuration = utils.releaseLock('sisyphus.bughunter.sitetestrun')
                    if lockDuration > datetime.timedelta(seconds=5):
                        self.logMessage("runTest: releaseLock('sisyphus.bughunter.sitetestrun') duration: %s" % lockDuration)


    def reloadProgram(self, db_available=True):

        if db_available and self.testrun_row:
            self.testrun_row.state = 'waiting'
            self.testrun_row.worker = None
            self.testrun_row.save()
            self.testrun_row = None

        worker.Worker.reloadProgram(self, db_available=db_available)

    def freeOrphanJobs(self):

        """
        Reset the worker and state of any executing jobs whose worker's are not active.
        """

        if not utils.getLock('sisyphus.bughunter.sitetestrun', 300):
            self.debugMessage("freeOrphanJobs: lock timed out")
        else:
            try:
                # Retrieve the SiteTestRun rows individually and check
                # the worker state separately to prevent table locks from
                # causing a deadlock.
                sitetestrun_rows = (models.SiteTestRun.objects.
                                    filter(state__exact='executing').
                                    filter(worker__isnull=False))
                for sitetestrun_row in sitetestrun_rows:
                    try:
                        if sitetestrun_row.worker.state in ('waiting', 'dead', 'zombie', 'disabled'):
                            sitetestrun_row.worker = None
                            sitetestrun_row.state = 'waiting'
                            sitetestrun_row.save()
                    except sisyphus.webapp.bughunter.models.Worker.DoesNotExist:
                        sitetestrun_row.worker = None
                        sitetestrun_row.state = 'waiting'
                        sitetestrun_row.save()

            except:
                raise
            finally:
                lockDuration = utils.releaseLock('sisyphus.bughunter.sitetestrun')
                if lockDuration > datetime.timedelta(seconds=5):
                    self.logMessage("freeOrphanJobs: releaseLock('sisyphus.bughunter.sitetestrun') duration: %s" % lockDuration)

    def getJob(self):
        """
        return a signature unprocessed by this worker
        matches on priority, os_name, cpu_name, os_version.
        """

        sitetestrun_row = None
        locktimeout     = 300

        for priority in 0, 1, 3:
            if not utils.getLock('sisyphus.bughunter.sitetestrun', locktimeout):
                self.debugMessage("getJob: lock timed out")
            else:
                try:
                    sitetestrun_row = models.SiteTestRun.objects.filter(
                        priority = priority,
                        state__exact = "waiting",
                        os_name__exact = self.os_name,
                        os_version__exact = self.os_version,
                        cpu_name__exact = self.cpu_name,
                        build_cpu_name__exact = self.build_cpu_name,
                        buildtype__in = tuple(self.buildspecs.split(','))
                    )[0]
                    sitetestrun_row.worker = self.worker_row
                    sitetestrun_row.state = 'executing'
                    sitetestrun_row.save()
                    break

                except IndexError:
                    sitetestrun_row = None

                except models.SiteTestRun.DoesNotExist:
                    sitetestrun_row = None

                finally:
                    lockDuration = utils.releaseLock('sisyphus.bughunter.sitetestrun')
                    if lockDuration > datetime.timedelta(seconds=5):
                        self.logMessage("getJobs: releaseLock('sisyphus.bughunter.sitetestrun') duration: %s" % lockDuration)
                    self.debugMessage('getJob: %s %s' % (sitetestrun_row, lockDuration))

        return sitetestrun_row

    def doWork(self):

        waittime  = 0

        build_checkup_interval = datetime.timedelta(hours=3)

        checkup_interval  = datetime.timedelta(minutes=5)
        last_checkup_time = datetime.datetime.now() - 2*checkup_interval

        zombie_interval   = datetime.timedelta(hours=self.zombie_time)
        last_zombie_time  = datetime.datetime.now() - 2*zombie_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate()
                last_checkup_time = datetime.datetime.now()

            if datetime.datetime.now() - last_zombie_time > zombie_interval:
                self.killZombies()
                self.freeOrphanJobs()
                last_zombie_time = datetime.datetime.now()
                # Reset the zombie_interval so that on average only one worker kills
                # zombies per zombie_time.
                worker_count  = models.Worker.objects.filter(worker_type__exact = self.worker_type,
                                                             state__in = ('waiting',
                                                                          'building',
                                                                          'installing',
                                                                          'executing',
                                                                          'testing',
                                                                          'completed')).count()
                zombie_interval  = datetime.timedelta(hours = worker_count * self.zombie_time)

            sys.stdout.flush()
            time.sleep(waittime)
            waittime = 0

            self.testrun_row = self.getJob()
            if not self.testrun_row:
                if self.state != "waiting":
                    self.logMessage('No signatures available to process, going idle.')
                waittime      = 900
                self.state    = "waiting"
                self.save()
                continue

            self.product   = self.testrun_row.product
            self.branch    = self.testrun_row.branch
            self.buildtype = self.testrun_row.buildtype

            build_needed = self.isNewBuildNeeded(build_checkup_interval)

            if build_needed:
                if self.isBuilder:
                    if self.tinderbox:
                        self.getTinderboxProduct()
                        self.installBuild()
                    else:
                        self.publishNewBuild()
                elif self.build_row and self.build_row.buildavailable:
                    self.installBuild()

                if not self.build_date:
                    self.testrun_row.worker  = None
                    self.testrun_row.state   = 'waiting'
                    self.testrun_row.save()
                    self.state           = 'waiting'
                    self.testrun_row = None
                    self.save()
                    waittime = 300
                    continue

            if self.state == "waiting":
                self.logMessage('New signatures available to process, going active.')

            try:
                # XXX: extra_test_args should be something to pass parameters to the
                # test process.
                extra_test_args = None
                self.runTest(extra_test_args)
                if self.testrun_row:
                    self.testrun_row.state = 'completed'
                    self.testrun_row.save()
                self.state            = 'completed'
                self.testrun_row  = None
                self.save()
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception, e:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                if str(exceptionValue) == 'CrashWorker.runTest.FatalError':
                    raise
                self.logMessage("doWork: error in runTest. %s signature: %s, url: %s, exception: %s" %
                                (exceptionValue, self.testrun_row.socorro.signature, self.testrun_row.socorro.url, errorMessage))

                if exceptionType == OSError:
                    if (e.errno == 12 or
                        e.errno == 23 or
                        e.errno == 24):
                        # Either out of memory or too many open files. We
                        # can not reliably recover so just reload the
                        # program and start over.
                        try:
                            self.logMessage('runTest: %s, OSError.errno=%d. Restarting.' %
                                            (self.testrun_row.socorro.url, e.errno))
                        except:
                            # Just ignore the error if we can't log the problem.
                            pass
                        try:
                            self.reloadProgram()
                        except:
                            # Exit if we can't restart the program.
                            sys.exit(2)
            finally:
                if self.testrun_row:
                    self.testrun_row.state = 'waiting'
                    self.testrun_row.save()
                self.state            = 'completed'
                self.testrun_row  = None
                self.save()

program_info.init(globals())

def main():

    global this_worker

    usage = '''usage: %prog [options]
'''
    parser = OptionParser(usage=usage)

    parser.add_option('--userhook', action='store', type='string',
                      dest='userhook',
                      help='userhook to execute for each loaded page. ' +
                      'Defaults to test-crash-on-load.js.',
                      default='test-crash-on-load.js')

    parser.add_option('--page-timeout', action='store', type='int',
                      dest='page_timeout',
                      help='Time in seconds before a page load times out. ' +
                      'Defaults to 180 seconds',
                      default=180)

    parser.add_option('--site-timeout', action='store', type='int',
                      dest='site_timeout',
                      help='Time in seconds before a site load times out. ' +
                      'Defaults to 300 seconds',
                      default=300)

    parser.add_option('--invisible', action='store_true',
                      dest='invisible',
                      help='Flag to start Spider with browser content set to invisible. ' +
                      'Defaults to False.',
                      default=False)

    parser.add_option('--build', action='store_true',
                      dest='build',
                      default=False, help='Perform own builds')

    parser.add_option('--no-upload', action='store_true',
                      dest='no_upload',
                      default=False, help='Do not upload completed builds')

    parser.add_option('--nodebug', action='store_false',
                      dest='debug',
                      default=False,
                      help='default - no debug messages')

    parser.add_option('--debug', action='store_true',
                      dest='debug',
                      help='turn on debug messages')

    parser.add_option('--processor-type', action='store', type='string',
                       dest='processor_type',
                       help='Override default processor type: intel32, intel64, amd32, amd64',
                       default=None)

    parser.add_option('--symbols-paths', action='store', type='string',
                       dest='symbols_paths',
                       help='Space delimited list of paths to third party symbols. Defaults to /mozilla/flash-symbols',
                       default='/mozilla/flash-symbols')

    parser.add_option('--do-not-reproduce-bogus-signatures', action='store_true',
                       dest='do_not_reproduce_bogus_signatures',
                       help='Do not attempt to reproduce crashes with signatures of the form (frame)',
                       default=False)

    parser.add_option('--buildspec', action='append',
                       dest='buildspecs',
                       help='Build specifiers: Restricts the builds tested by '
                      'this worker to one of opt, debug, opt-asan, debug-asan. '
                      'Defaults to all build types specified in the Branches '
                      'To restrict this worker to a subset of build specifiers, '
                      'list each desired specifier in separate '
                      '--buildspec options.',
                       default=[])

    parser.add_option('--tinderbox', action='store_true',
                       dest='tinderbox',
                       help='If --build is specified, this will cause the '
                      'worker to download the latest tinderbox builds '
                      'instead of performing custom builds. '
                      'Defaults to False.',
                       default=False)

    try:
        (options, args) = parser.parse_args()
    except:
        raise Exception("NormalExit")

    os.environ["TEST_TOPSITE_TIMEOUT"]      = str(options.site_timeout)
    os.environ["TEST_TOPSITE_PAGE_TIMEOUT"] = str(options.page_timeout)

    exception_counter = 0

    this_worker     = CrashTestWorker(options)

    this_worker.logMessage('starting worker %s %s %s with program dated %s' %
                          (this_worker.os_name, this_worker.os_version, this_worker.cpu_name,
                           time.ctime(program_info.programModTime)))
    while True:
        try:
            this_worker.doWork()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:

            if this_worker.testrun_row:
                this_worker.testrun_row.state = 'waiting'
                this_worker.testrun_row.worker = None
                this_worker.testrun_row.save()
                this_worker.testrun_row = None
                this_worker.save()

            exception_counter += 1
            if exception_counter > 100:
                print "Too many errors. Terminating."
                sys.exit(2)

            exceptionType, exceptionValue, errorMessage = utils.formatException()

            if str(exceptionValue) == 'CrashWorker.runTest.FatalError':
                raise

            if str(exceptionValue) == 'WorkerInconsistent':
                # If we were disabled, sleep for 5 minutes and check our state again.
                # otherwise restart.
                if this_worker.state == "disabled":
                    while True:
                        time.sleep(300)
                        curr_worker_row = models.Worker.objects.get(pk = this_worker.worker_row.id)
                        if curr_worker_row.state != "disabled":
                            this_worker.state = "waiting"
                            break

            this_worker.logMessage('main: exception %s: %s' % (str(exceptionValue), errorMessage))

            time.sleep(60)


if __name__ == "__main__":
    restart = True
    this_worker = None
    db_available = True

    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        restart = False
    except django.db.utils.OperationalError, e:
        db_available = False
        print '%s %s: Will attempt to restart in 300 seconds' % (datetime.datetime.now(), e)
        time.sleep(300)
    except:
        exceptionType, exceptionValue, errorMessage = utils.formatException()
        exceptionValue = str(exceptionValue)
        if exceptionValue not in "0,NormalExit":
            print 'main: exception exceptionType: %s: exceptionValue: %s, errorMessage: %s' % (exceptionType, exceptionValue, errorMessage)

        if exceptionValue == 'CrashWorker.runTest.FatalError':
            restart = False

    # kill any test processes still running.
    if db_available and this_worker:
        this_worker.killTest()

    if restart:
        # continue trying to log message until it succeeds.
        if not this_worker:
            utils.reloadProgram(program_info)
        else:
            if db_available:
                this_worker.logMessage('Program restarting')
            this_worker.reloadProgram(db_available=db_available)

    if db_available:
        this_worker.logMessage('Program terminating')
        this_worker.state = 'dead'
        this_worker.save()
