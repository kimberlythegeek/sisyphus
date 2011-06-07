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
# The Original Code is Mozilla Crash Automation Testing.
#
# The Initial Developer of the Original Code is
# Mozilla Corporation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
# Bob Clary
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

from optparse import OptionParser
import os
import stat
import time
import datetime
import sys
import subprocess
import re

import platform
import base64 # for encoding document attachments.
import urlparse
import urllib
import glob

sisyphus_dir     = os.environ["TEST_DIR"]
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

from django.db import connection
import sisyphus.webapp.settings
sisyphus_url      = os.environ["SISYPHUS_URL"]
post_files_url    = sisyphus_url + '/post_files/'

from sisyphus.webapp.bughunter import models
from sisyphus.automation import utils, worker, program_info

os.environ["TEST_TOPSITE_TIMEOUT"]="300"
os.environ["TEST_TOPSITE_PAGE_TIMEOUT"]="120"
os.environ["XPCOM_DEBUG_BREAK"]="stack"
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

        # self.invisible is the optional argument to the top-sites.sh test script
        # to make Spider hide the content being loaded.
        if options.invisible:
            self.invisible = ' -i '
        else:
            self.invisible = ''

    def runTest(self, extra_test_args):

        self.debugMessage("testing firefox %s %s %s" % (self.branch, self.buildtype, self.testrun_row.socorro.url))
        self.state        = "testing"
        self.datetime     = utils.getTimestamp()
        self.save()

        # kill any test processes still running.
        test_process_dict = self.psTest()
        if test_process_dict:
            for test_process in test_process_dict:
                self.logMessage('runTest: test process running before test: pid: %s : %s' % (test_process, test_process_dict[test_process]))
            self.killTest()

        socorro_row = self.testrun_row.socorro

        url = utils.encodeUrl(socorro_row.url)

        timestamp = utils.getTimestamp()

        self.testrun_row.changeset = self.build_row.changeset
        self.testrun_row.datetime  = timestamp
        self.testrun_row.extra_test_args = extra_test_args
        self.testrun_row.save()

        page               = "startup"
        executablepath     = ""
        profilename        = ""
        page_http_403      = False # page returned 403 Forbidden
        reFatalError       = re.compile(r'FATAL ERROR')
        reExecutablePath   = re.compile(r'^environment: TEST_EXECUTABLEPATH=(.*)')
        reProfileName      = re.compile(r'^environment: TEST_PROFILENAME=(.*)')
        reAssertionFail    = re.compile(r'^(Assertion failure: .*), at .*')
        reABORT            = re.compile(r'^.?###\!\!\! (ABORT: .*), file (.*), line [0-9]+.*')
        reASSERTION        = re.compile(r'^.?###\!\!\! ASSERTION: (.*), file (.*), line [0-9]+.*')
        reValgrindLeader   = re.compile(r'^==[0-9]+==')
        reSpiderBegin      = re.compile(r'^Spider: Begin loading (.*)')
        reSpider           = re.compile(r'^Spider:')
        reUrlExitStatus    = re.compile(r'^(http.*): EXIT STATUS: (.*) [(].*[)].*')

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

        data    = u""

        # attempt to silence undefined errors if exception thrown during communicate.
        stdout = ''
        stderr = ''

        fatal_error = False

        proc = subprocess.Popen(
            [
                "./bin/tester.sh",
                "-t",
                "tests/mozilla.org/top-sites/test.sh -u " +
                url +
                self.invisible + " -H -D 1 -h " + self.userhook,
                self.product,
                self.branch,
                self.buildtype
                ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            env=environment)

        try:
            stdout, stderr = proc.communicate()
        except KeyboardInterrupt, SystemExit:
            raise
        except:

            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('runTest: exception: %s, %s' % (exceptionValue, errorMessage))

            if errorMessage.find('filedescriptor out of range') != -1:
                self.logMessage('filedescriptors %d out of range. Restarting.' %
                                utils.openFileDescriptorCount())
                # Closing file descriptors and trying again does not
                # fix the issue on Windows. Just restart the program.
                self.reloadProgram()

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

                match = reFatalError.match(line)
                if match:
                    fatal_error = True
                    self.logMessage("runTest: %s" % line)

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
                    self.process_assertions(timestamp, assertion_dict, page, "crashtest", extra_test_args)
                    valgrind_list = self.parse_valgrind(valgrind_text)
                    self.process_valgrind(timestamp, valgrind_list, page, "crashtest", extra_test_args)

                    assertion_dict   = {}
                    valgrind_text    = ""
                    valgrind_list    = None
                    if match:
                        page = match.group(1).strip()
                    continue

                match = reHTTP403.match(line)
                if match:
                    page_http_403 = True
                    continue

                match = reAssertionFail.match(line)
                if match:
                    self.testrun_row.fatal_message = match.group(1)
                    continue

                match = reABORT.match(line)
                if match:
                    self.testrun_row.fatal_message = match.group(1)
                    continue

                match = reASSERTION.match(line)
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

            baselogfilename = os.path.basename(logfilename)
            loguploadpath = 'logs/' + baselogfilename[:13] # CCYY-MM-DD-HH
            dmpuploadpath = 'minidumps/' + baselogfilename[:13] # CCYY-MM-DD-HH
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

            symbolsPath = os.path.join(executablepath, 'crashreporter-symbols')

            self.process_dump_files(timestamp, profilename, page, symbolsPath, dmpuploadpath)


        hung_process = False
        test_process_dict = self.psTest()
        if test_process_dict:
            hung_process = True
            for test_process in test_process_dict:
                self.logMessage('runTest: test process still running: pid: %s : %s' % (test_process, test_process_dict[test_process]))
            self.killTest()

        if hung_process:
            if self.testrun_row.exitstatus:
                self.testrun_row.exitstatus += ' HANG'
            else:
                self.testrun_row.exitstatus = 'HANG'

        self.testrun_row.save()

        if self.testrun_row.crashed and self.testrun_row.priority not in '01':

            # Generate new priority 0 jobs for the other operating systems if the job
            # was not a priority 0 or priority 1 (user submitted).

            try:
                worker_rows   = models.Worker.objects.filter(worker_type__exact = self.worker_type)
                branches_rows = models.Branch.objects.all()

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
                        worker_row.cpu_name   == self.cpu_name and
                        worker_row.os_version == self.os_version):
                        continue

                    worker_os_cpu_key = worker_row.os_name + worker_row.cpu_name + worker_row.os_version
                    if worker_os_cpu_key in os_cpu_hash:
                        # we've already emitted a signature for this os/cpu.
                        continue

                    os_cpu_hash[worker_os_cpu_key] = 1

                    for branch_row in branches_rows:
                        if branch_row.product != self.product:
                            continue

                        # PowerPC is not supported after Firefox 3.6
                        if branch_row.major_version > '0306' and worker_row.cpu_name == 'ppc':
                            continue

                        old_test_run = self.testrun_row

                        new_socorro_row = models.SocorroRecord(
                            signature           = old_test_run.socorro.signature,
                            url                 = page,
                            uuid                = '',
                            client_crash_date   = '',
                            date_processed      = '',
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
                            build_cpu_name    = None,
                            worker            = None,
                            socorro           = new_socorro_row,
                            changeset         = None,
                            datetime          = utils.getTimestamp(),
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

            except KeyboardInterrupt, SystemExit:
                raise
            except:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                self.logMessage('runTest: unable to duplicate signature %s for reproduction: %s' % (self.testrun_row, errorMessage))

        # process any remaining assertion or valgrind messages.
        self.process_assertions(timestamp, assertion_dict, page, "crashtest", extra_test_args)
        valgrind_list = self.parse_valgrind(valgrind_text)
        self.process_valgrind(timestamp, valgrind_list, page, "crashtest", extra_test_args)

        # A resource was forbidden. Rather than continuing to attempt
        # to load a forbidden url, remove all waiting jobs for it.
        if page_http_403:
            if not utils.getLock('sisyphus.bughunter.sitetestrun', 300):
                self.debugMessage("runTest: lock timed out attempting to remove forbidden urls")
            else:
                try:
                    cursor = connection.cursor()
                    cursor.execute("""DELETE SocorroRecord, SiteTestRun FROM SocorroRecord, SiteTestRun WHERE
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


    def reloadProgram(self):

        if self.testrun_row:
            self.testrun_row.state = 'waiting'
            self.testrun_row.datetime = utils.getTimestamp()
            self.testrun_row.worker = None
            self.testrun_row.save()
            self.testrun_row = None

        worker.Worker.reloadProgram(self)

    def freeOrphanJobs(self):

        """
        Reset the worker and state of any executing jobs whose worker's are not active.
        """

        if not utils.getLock('sisyphus.bughunter.sitetestrun', 300):
            self.debugMessage("freeOrphanJobs: lock timed out")
        else:
            try:
                timestamp = utils.getTimestamp()
                #sitetestrun_rows = models.SiteTestRun.objects.filter(state__exact = 'executing', worker__state__in ('waiting', 'dead', 'zombie', 'disabled')).update(worker = None, state = 'waiting', datetime = timestamp)
                sitetestrun_rows = models.SiteTestRun.objects.filter(state__exact = 'executing')
                sitetestrun_rows = sitetestrun_rows.filter(worker__state__in = ('waiting', 'dead', 'zombie', 'disabled'))
                sitetestrun_rows.update(worker = None, state = 'waiting', datetime = timestamp)
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

        locktimeout     = 300

        if not utils.getLock('sisyphus.bughunter.sitetestrun', locktimeout):
            self.debugMessage("getJob: lock timed out")
        else:
            try:
                sitetestrun_row = models.SiteTestRun.objects.filter(state__exact = "waiting",
                                                                    os_name__exact = self.os_name,
                                                                    os_version__exact = self.os_version,
                                                                    cpu_name__exact = self.build_cpu_name).order_by('priority')[0]
                sitetestrun_row.worker = self.worker_row
                sitetestrun_row.state = 'executing'
                sitetestrun_row.build_cpu_name = self.build_cpu_name
                sitetestrun_row.save()

            except IndexError:
                sitetestrun_row = None
                pass

            except models.SiteTestRun.DoesNotExist:
                sitetestrun_row = None
                pass

            finally:
                lockDuration = utils.releaseLock('sisyphus.bughunter.sitetestrun')
                if lockDuration > datetime.timedelta(seconds=5):
                    self.logMessage("getJobs: releaseLock('sisyphus.bughunter.sitetestrun') duration: %s" % lockDuration)

        return sitetestrun_row

    def doWork(self):

        waittime  = 0

        build_checkup_interval = datetime.timedelta(hours=3)
        checkup_interval       = datetime.timedelta(minutes=5)
        last_checkup_time      = datetime.datetime.now() - 2*checkup_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate()
                self.killZombies()
                self.freeOrphanJobs()
                last_checkup_time = datetime.datetime.now()

            sys.stdout.flush()
            time.sleep(waittime)
            waittime = 0

            self.testrun_row = self.getJob()
            if not self.testrun_row:
                if self.state != "waiting":
                    self.logMessage('No signatures available to process, going idle.')
                major_version = None
                branch_data   = None
                branch        = None
                waittime      = 900
                self.state    = "waiting"
                self.datetime = utils.getTimestamp()
                self.save()
                continue

            major_version  = self.testrun_row.major_version
            self.product   = self.testrun_row.product
            self.branch    = self.testrun_row.branch
            self.buildtype = self.testrun_row.buildtype

            build_needed = self.isNewBuildNeeded(build_checkup_interval)

            if build_needed:
                if self.isBuilder:
                    self.publishNewBuild()
                elif self.build_row and self.build_row.buildavailable:
                    self.installBuild()

                if not self.build_date:
                    self.testrun_row.worker  = None
                    self.testrun_row.state   = 'waiting'
                    self.testrun_row.save()
                    self.state           = 'waiting'
                    self.datetime        = utils.getTimestamp()
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
            except KeyboardInterrupt, SystemExit:
                raise
            except:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                if str(exceptionValue) == 'CrashWorker.runTest.FatalError':
                    raise
                self.logMessage("doWork: error in runTest. %s signature: %s, url: %s, exception: %s" %
                                (exceptionValue, self.testrun_row.socorro.signature, self.testrun_row.socorro.url, errorMessage))
            finally:
                if self.testrun_row:
                    self.testrun_row.state = 'completed'
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

    parser.add_option('--invisible', action='store_true',
                      dest='invisible',
                      help='Flag to start Spider with browser content set to invisible. ' +
                      'Defaults to False.',
                      default=False)

    parser.add_option('--build', action='store_true',
                      default=False, help='Perform own builds')

    parser.add_option('--nodebug', action='store_false',
                      dest='debug',
                      default=False,
                      help='default - no debug messages')

    parser.add_option('--debug', action='store_true',
                      dest='debug',
                      help='turn on debug messages')

    try:
        (options, args) = parser.parse_args()
    except:
        raise Exception("NormalExit")

    exception_counter = 0

    this_worker     = CrashTestWorker(options)

    this_worker.logMessage('starting worker %s %s %s with program dated %s' %
                          (this_worker.os_name, this_worker.os_version, this_worker.cpu_name,
                           time.ctime(program_info.programModTime)))
    while True:
        try:
            this_worker.doWork()
        except KeyboardInterrupt, SystemExit:
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
                        curr_worker_row = models.Worker.objects.get(pk = self.hostname)
                        if curr_worker_row.state != "disabled":
                            this_worker.state = "waiting"
                            break

            this_worker.logMessage('main: exception %s: %s' % (str(exceptionValue), errorMessage))

            time.sleep(60)


if __name__ == "__main__":
    try:
        this_worker = None
        restart     = True
        main()
    except KeyboardInterrupt, SystemExit:
        restart = False
    except:
        exceptionType, exceptionValue, errorMessage = utils.formatException()
        if str(exceptionValue) not in "0,NormalExit":
            print ('main: exception %s: %s' % (str(exceptionValue), errorMessage))

        if str(exceptionValue) == 'CrashWorker.runTest.FatalError':
            restart = False

    # kill any test processes still running.
    if this_worker:
        this_worker.killTest()

    if this_worker is None:
        sys.exit(2)

    if restart:
        # continue trying to log message until it succeeds.
        this_worker.logMessage('Program restarting')
        this_worker.reloadProgram()
    else:
        this_worker.logMessage('Program terminating')
        this_worker.state = 'dead'
        this_worker.save()
