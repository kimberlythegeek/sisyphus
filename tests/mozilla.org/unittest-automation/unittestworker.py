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
import base64 # for encoding document attachments.
import urllib
import glob
import signal
import tempfile

startdir       = os.getcwd()
programPath    = os.path.abspath(os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])), os.path.basename(sys.argv[0])))

sisyphus_dir     = os.environ["TEST_DIR"]
sys.path.append(os.path.join(sisyphus_dir,'bin'))

import sisyphus.utils
import sisyphus.couchdb
import sisyphus.bugzilla
import sisyphus.worker

options          = None

os.chdir(sisyphus_dir)

stackwalkPath = os.environ.get('MINIDUMP_STACKWALK', "/usr/local/bin/minidump_stackwalk")
# if MINIDUMP_STACKWALK was not specified, set it to the default value if it exists.
# this will pass it on to the unit test runners.
if os.path.exists(stackwalkPath):
    os.environ['MINIDUMP_STACKWALK'] = stackwalkPath

class UnitTestWorker(sisyphus.worker.Worker):

    def __init__(self, startdir, programPath, couchserveruri, couchdbname, worker_comment, debug):
        sisyphus.worker.Worker.__init__(self, "unittest", startdir, programPath, couchserveruri, couchdbname, worker_comment, debug)

    def checkForUpdate(self, job_doc):
        if os.stat(self.programPath)[stat.ST_MTIME] != self.programModTime:
            message = 'checkForUpdate: Program change detected. Reloading from disk. %s %s' % (sys.executable, sys.argv)
            self.logMessage(message)
            if self.document is not None:
                try:
                    self.document['state'] = message
                    self.updateWorker(self.document)
                except:
                    pass
            if job_doc is not None:
                # reinsert the job
                self.testdb.createDocument(job_doc)
            self.reloadProgram()

    def runTest(self, product, branch, buildtype, test, extra_test_args):

        # kill any test processes still running.
        self.killTest()

        timestamp = sisyphus.utils.getTimestamp()

        result_doc = {
            "type"            : "result_header_unittest",
            "product"         : product,
            "branch"          : branch,
            "buildtype"       : buildtype,
            "test"            : test,
            "extra_test_args" : extra_test_args,
            "os_name"         : self.document["os_name"],
            "os_version"      : self.document["os_version"],
            "cpu_name"        : self.document["cpu_name"],
            "worker_id"       : self.document["_id"],
            "changeset"       : self.document[branch]["changeset"],
            "datetime"        : timestamp,
            "exitstatus"      : "",
            "returncode"      : None,
            }

        self.testdb.createDocument(result_doc)

        # The test frameworks do not bracket test results within begin/end
        # blocks (with the exception of the jstests). Instead they run the
        # test and then emit a test result line after the test has
        # completed. Therefore we collect information about a test until
        # we get a match for a test result then emit the appropriate
        # result documents for assertions, valgrind messages, test
        # results. Typically crashes will occur before the test result is
        # emitted in the log, so we instead will list the test immediately
        # prior to the crashing test.

        executablepath   = None
        profilename      = ""
        reExecutablePath = re.compile(r'^environment: executablepath=(.*)')
        reProfileName    = re.compile(r'^environment: profilename=(.*)')
        reAssertionFail  = re.compile(r'^Assertion fail.*')
        reASSERTION      = re.compile(r'^.?###\!\!\! ASSERTION: (.*), file (.*), line [0-9]+.*')
        reValgrindLeader = re.compile(r'^==[0-9]+==')
        # reftest
        # REFTEST TEST-START | testid
        #       action: process previously collected messages
        #               for previous testid, set current testid.
        # REFTEST TEST-PASS | testid | message
        # REFTEST TEST-KNOWN-FAIL | testid | message
        #       action: If all results selected, output unittest result.
        # REFTEST TEST-UNEXPECTED-FAIL | testid | message
        #       action: Output unittest result.
        reReftestStart   = re.compile(r'REFTEST TEST-START \| (.*)')
        reReftestResult  = re.compile(r'REFTEST TEST-(.*?) \| (.*?) \| (.*)')
        # mochitest
        # 9999 INFO TEST-START | testid...
        #       action: process previously collected messages
        #               for previous testid, set current testid.
        # 9999 INFO TEST-PASS | testid | message
        # 9999 INFO TEST-KNOWN-FAIL | testid | message
        #       action: If all results selected, output unittest result.
        # 9999 ERROR TEST-UNEXPECTED-FAIL | testid | message
        #       action: Output unittest result.
        reMochitestStart = re.compile(r'[0-9]+ INFO TEST-START \| (.*)')
        reMochitestInfo = re.compile(r'[0-9]+ INFO TEST-INFO')
        reMochitestResultPass = re.compile(r'[0-9]+ INFO TEST-(.*?) \| (.*?) \| (.*)')
        reMochitestResultError = re.compile(r'[0-9]+ ERROR TEST-(.*?) \| (.*?) \| (.*)')
        reMochitestEnd = re.compile(r'[0-9]+ INFO TEST-END \| (.*)')
        # xpctest
        # TEST_PASS | testid | message
        # TEST-KNOWN-FAIL | testid | message # this may not be valid.
        #       action: process previously collected messages 
        #               for this testid.
        # TEST-UNEXPECTED-FAIL | testid | message
        #               includes overall test run message not related to xpctests.
        #       action: process previously collected messages
        #               for this testid.
        reXpctestStart  = re.compile(r'TEST-(.*?) \| (.*?) \| running test')
        reXpctestResult  = re.compile(r'TEST-(.*?) \| (.*?) \| (.*)')

        # buffers to hold assertions and valgrind messages until
        # a test result is seen in the output.
        assertion_list = []
        valgrind_text  = ""

        size    = 0         # current log size
        maxsize = 0xfffffff # maximum log size ~ 268435455
        data    = u""       # log buffer

        # update the worker every hour to keep from being marked a zombie.
        update_interval = datetime.timedelta(minutes=60)
        last_update_time = datetime.datetime.now() - 2*update_interval

        # time out the unittest after unittest_timeout seconds
        unittest_timeout   = datetime.timedelta(seconds = options.global_timeout * 3600)
        unittest_starttime = datetime.datetime.now()
        unittest_endtime   = unittest_starttime + unittest_timeout

        # XXX: using set-build-env.sh is a kludge needed on windows which
        # allows us to use cygwin to setup the msys mozilla-build
        # environment and call make using msys.  this is a problem in that
        # the processes become disconnected and the msys processes are
        # orphans with respect to cygwin.  killing the process created by
        # Popen will not kill the msys processes or firefox processes
        # created during the make.

        logfile = tempfile.NamedTemporaryFile()

        proc = subprocess.Popen(
            [
                "./bin/set-build-env.sh",
                "-p", product,
                "-b", branch,
                "-T", buildtype,
                "-c", "make -C firefox-%s EXTRA_TEST_ARGS=\"%s\" %s" % (buildtype, extra_test_args, test)
                ],
            bufsize=1, # line buffered
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        unittest_id = 'startup'

        try:
            # initial read timeout is the global timeout for the unittest
            line = sisyphus.utils.timedReadLine(proc.stdout, unittest_timeout.seconds)
            line = sisyphus.utils.makeUnicodeString(line)

            while line:

                current_time = datetime.datetime.now()

                if current_time - last_update_time > update_interval:
                    self.document["datetime"] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    last_update_time = datetime.datetime.now()

                if current_time - unittest_starttime > unittest_timeout:
                    raise Exception('UnitTestTimeout')

                if size > maxsize:
                    raise Exception('UnitTestSizeError')

                size += len(line)

                logfile.write(line.encode('utf-8'))

                if not executablepath:
                    match = reExecutablePath.match(line)
                    if match:
                        executablepath = match.group(1)

                if not profilename:
                    match = reProfileName.match(line)
                    if match:
                        profilename = match.group(1)

                next_unittest_id = None
                unittest_result = 'Unknown'
                unittest_message = None
                # process_messages controls when we dump assertions and valgrinds that
                # we have collected so far. Dump them whenever we see a new test.
                process_messages = False

                match = reReftestStart.match(line)
                if match:
                    process_messages = True
                    next_unittest_id = match.group(1)
                else:
                    # reReftestResult also matches reReftestStart lines so must be tested
                    # only after reRefTestStart has been excluded.
                    match = reReftestResult.match(line)
                    if match:
                        unittest_result = match.group(1)
                        unittest_id = match.group(2)
                        unittest_message = match.group(3)
                    else:
                        match = reMochitestInfo.match(line)
                        if match:
                            pass # ignore TEST-INFO lines. Need to test first since otherwise
                                 # would test results would match test info lines.
                        else:
                            match = reMochitestStart.match(line)
                            if match:
                                process_messages = True
                                next_unittest_id = match.group(1)
                            else:
                                match = reMochitestEnd.match(line)
                                if match:
                                    pass # ignore TEST-END lines.
                                else:
                                    match = reMochitestResultPass.match(line)
                                    if match:
                                        unittest_result = match.group(1)
                                        unittest_id = match.group(2)
                                        unittest_message = match.group(3)
                                    else:
                                        match = reMochitestResultError.match(line)
                                        if match:
                                            unittest_result = match.group(1)
                                            unittest_id = match.group(2)
                                            unittest_message = match.group(3)
                                        else:
                                            match = reXpctestStart.match(line)
                                            if match:
                                                process_messages = True
                                                next_unittest_id = match.group(2)
                                            else:
                                                match = reXpctestResult.match(line)
                                                if match:
                                                    process_messages = True
                                                    unittest_result = match.group(1)
                                                    unittest_id = match.group(2)
                                                    unittest_message = match.group(3)

                if process_messages:
                    self.process_assertions(result_doc["_id"], product, branch, buildtype, timestamp, assertion_list, unittest_id, test, extra_test_args)
                    valgrind_list = self.parse_valgrind(valgrind_text)
                    self.process_valgrind(result_doc["_id"], product, branch, buildtype, timestamp, valgrind_list, unittest_id, test,  extra_test_args)
                    assertion_list   = []
                    valgrind_text    = ""
                    unittest_id = next_unittest_id

                if (unittest_id and unittest_result != 'Unknown' and
                    (options.all_test_results or re.search('UNEXPECTED', unittest_result))):
                    # by default, only output unittest results if they are
                    # unexpected
                    result_unittest_doc = {
                        "type"            : "result_unittest",
                        "product"         : product,
                        "branch"          : branch,
                        "buildtype"       : buildtype,
                        "test"            : test,
                        "extra_test_args" : extra_test_args,
                        "os_name"         : self.document["os_name"],
                        "os_version"      : self.document["os_version"],
                        "cpu_name"        : self.document["cpu_name"],
                        "worker_id"       : self.document["_id"],
                        "datetime"        : timestamp,
                        "unittest_id"     : unittest_id,
                        "unittest_result" : unittest_result,
                        "unittest_message" : unittest_message
                        }
                    self.testdb.createDocument(result_unittest_doc)

                match = reASSERTION.match(line)
                if match:
                    # record the assertion for later output when we know the test
                    assertion_list.append({
                            "message" : match.group(1),
                            "file"    : re.sub('^([a-zA-Z]:/|/[a-zA-Z]/)', '/', re.sub(r'\\', '/', match.group(2))),
                            "datetime" : timestamp,
                            })

                match = reValgrindLeader.match(line)
                if match:
                    valgrind_text += line

                # do we really want|need this considering cairo's pollution
                # of the assertion failure space?
                match = reAssertionFail.match(line)
                if match:
                    result_doc["assertionfail"] = match.group(0)

                # subsequent read timeout is the remaining time before the
                # global timeout for the unittest.
                read_timeout = (unittest_endtime - current_time).seconds
                line = sisyphus.utils.timedReadLine(proc.stdout, read_timeout)
                line = sisyphus.utils.makeUnicodeString(line)

            try:
                def timedProcCommunicate_handler(signum, frame):
                    raise Exception('ProcCommunicateTimeout')

                signal.signal(signal.SIGALRM, timedProcCommunicate_handler)
                signal.alarm(read_timeout)
                proc.communicate()
                signal.alarm(0)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType,
                                                              exceptionValue,
                                                              exceptionTraceback)
                self.logMessage("runTest: %s %s %s: exception: %s" %
                                (product, branch, test, errorMessage))

        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            errorMessage = sisyphus.utils.formatException(exceptionType,
                                                          exceptionValue,
                                                          exceptionTraceback)
            if proc.poll() is None:
                self.logMessage("runTest: %s %s %s: exception %s. killing process" %
                                (product, branch, test, errorMessage))
                self.killTest()

            if exceptionType == KeyboardInterrupt:
                raise

        if proc.poll() is None:
            self.logMessage("runTest: %s %s %s: process not terminated cleanly. killing process." %
                            (product, branch, test))
            self.killTest()

        result_doc["returncode"] = proc.poll()
        result_doc["exitstatus"] += sisyphus.utils.convertReturnCodeToExitStatusMessage(proc.returncode)

        if proc.returncode == -2:
            raise KeyboardInterrupt

        result_doc = self.testdb.saveFileAttachment(result_doc, 'log', logfile.name, 'text/plain', True, True)
        logfile.close()
        if os.path.exists(logfile.name):
            os.unlink(logfile.name)

        self.testdb.updateDocument(result_doc)

        # process any valgrind messages not associated with a test.
        self.process_assertions(result_doc["_id"], product, branch, buildtype, timestamp, assertion_list, "shutdown", test, extra_test_args)
        valgrind_list = self.parse_valgrind(valgrind_text)
        self.process_valgrind(result_doc["_id"], product, branch, buildtype, timestamp, valgrind_list, "shutdown", test, extra_test_args)

    def doWork(self):

        product   = "firefox"
        buildtype = "debug"
        waittime  = 0
        job_doc   = None

        build_checkup_interval = datetime.timedelta(hours=3)
        checkup_interval = datetime.timedelta(minutes=5)
        last_checkup_time = datetime.datetime.now() - 2*checkup_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate(job_doc)
                self.testdb.checkDatabase()
                self.killZombies()
                last_checkup_time = datetime.datetime.now()

            sys.stdout.flush()
            time.sleep(waittime)
            waittime = 0

            if job_doc:
                build_doc    = self.BuildDocument(product, branch, buildtype,
                                                  self.document["os_name"], self.document["cpu_name"])
                build_needed = self.NewBuildNeeded(build_doc, build_checkup_interval)
            else:
                job_doc = self.getJob()
                if job_doc:
                    branch    = job_doc["branch"]
                    test      = job_doc["test"]
                    extra_test_args = job_doc["extra_test_args"]
                    build_doc    = self.BuildDocument(product, branch, buildtype,
                                                      self.document["os_name"], self.document["cpu_name"])
                    build_needed = self.NewBuildNeeded(build_doc, build_checkup_interval)

                    self.logMessage('beginning job firefox %s %s %s' % (branch, buildtype, test))
                else:
                    branch        = None
                    test          = None
                    extra_test_args = None
                    tests_doc    = self.testdb.getDocument("tests")
                    self.logMessage('creating new jobs.')
                    self.createJobs(tests_doc)
                    continue

            if (options.build and
                (build_needed or not self.document[branch]["builddate"] or
                 sisyphus.utils.convertTimestamp(self.document[branch]["builddate"]).day != datetime.date.today().day)):

                # The build stored in the builds database is stale and
                # needs to be rebuilt, or we are a builder and do not
                # have a local build. Build it ourselves and upload
                # it.

                self.update_bug_histories()

                build_doc = self.publishNewBuild(build_doc)
                if build_doc["state"] == "error":
                    # wait for five minutes if a build failure occurs
                    waittime = 300
                    # reinsert the job
                    self.testdb.createDocument(job_doc)
                    job_doc = None
            elif (not options.build and build_doc["buildavailable"] and
                  (not self.document[branch]["buildsuccess"] or
                   build_doc["builddate"] > self.document[branch]["builddate"])):

                # We are not a builder, and a build is available to
                # download and either we do not have a build or the
                # available build is newer. Download and install the
                # newer build.

                if not self.DownloadAndInstallBuild(build_doc):
                    # We failed to install the new build.
                    # reinsert the job
                    self.logMessage('doWork: failed downloading new %s %s %s build' %
                                    (product, branch, buildtype))
                    self.testdb.createDocument(job_doc)
                    job_doc = None

            elif (self.document[branch]["buildsuccess"]):

                # Either the build in the builds database and our local build are both current
                # or both are stale. Continue to test with a stale build until a fresh one becomes
                # available.
                self.document["state"]        = "testing firefox %s %s %s" % (branch, buildtype, test)
                self.document["datetime"]     = sisyphus.utils.getTimestamp()
                self.updateWorker(self.document)
                self.runTest(product, branch, buildtype, test, extra_test_args)
                job_doc = None
                self.logMessage('finishing job firefox %s %s %s' % (branch, buildtype, test))
            else:
                self.logMessage('doWork: no %s %s %s builds are available' % (product, branch, buildtype))
                time.sleep(300)


    def getJobs(self):
        """
        return rows of test jobs for this worker
        matching os_name, cpu_name, os_version
        """
        job_rows = None

        startkey = [self.document["os_name"], self.document["cpu_name"], self.document["os_version"]]
        endkey   = [self.document["os_name"], self.document["cpu_name"], self.document["os_version"], {}]

        job_rows = self.getRows(self.testdb.db.views.unittest.jobs, startkey=startkey, endkey=endkey)

        return job_rows

    def getJob(self):
        """
        return a test job for this worker
        matching os_name, cpu_name, os_version
        """
        job_doc = None

        job_rows = self.getJobs()

        for job_doc in job_rows:

            try:
                self.testdb.deleteDocument(job_doc)
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                if str(exceptionValue) == 'updateDocumentConflict':
                    self.debugMessage("getJob: race condition updateDocumentConflict attempting to delete job %s." % job_doc)
                    continue

                if str(exceptionValue) == 'deleteDocumentConflict':
                    self.debugMessage("getJob: race condition deleteDocumentConflict attempting to delete job %s." % job_doc)
                    continue

                raise

        self.debugMessage("getJob: returning job %s" % job_doc)

        return job_doc

    def createJobs(self, tests_doc):

        if "EXTRA_TEST_ARGS" in os.environ:
            extra_test_args = os.environ["EXTRA_TEST_ARGS"] + " "
        else:
            extra_test_args = ""

        if options.debugger:
             extra_test_args += "--debugger='" + options.debugger + "' "
             if options.debugger_args:
                  extra_test_args += "--debugger-args='" + options.debugger_args + "' "

        if options.test_timeout:
             extra_test_args += "--timeout=" + str(options.test_timeout) + " "

        os_name    = self.document["os_name"]
        os_version = self.document["os_version"]
        cpu_name   = self.document["cpu_name"]

        for branch in tests_doc["branches"]:
            for test in tests_doc["branches"][branch]:
                # special case chunking mochitest-plain
                if test != "mochitest-plain":
                    job_doc = {
                        "type"       : "job_unittest",
                        "os_name"    : os_name,
                        "os_version" : os_version,
                        "cpu_name"   : cpu_name,
                        "branch"     : branch,
                        "test"       : test,
                        "extra_test_args" : extra_test_args
                        }
                    self.testdb.createDocument(job_doc)
                else:
                    total_chunks = 10
                    for chunk in range(total_chunks):
                        chunk_options = '%s --total-chunks=%d --this-chunk=%d' % (extra_test_args, total_chunks, chunk+1)
                        job_doc = {
                            "type"       : "job_unittest",
                            "os_name"    : os_name,
                            "os_version" : os_version,
                            "cpu_name"   : cpu_name,
                            "branch"     : branch,
                            "test"       : test,
                            "extra_test_args" : chunk_options
                            }
                        self.testdb.createDocument(job_doc)

def main():
    global options, this_worker

    this_worker = None

    usage = '''usage: %prog [options]

Example:
%prog --couch` http://couchserver
'''
    parser = OptionParser(usage=usage)

    parser.add_option('--couch', action='store', type='string',
                      dest='couchserveruri',
                      help='uri to couchdb server')

    parser.add_option('--database', action='store', type='string',
                      dest='databasename',
                      help='name of database, defaults to sisyphus.',
                      default='sisyphus')

    parser.add_option('--comment', action='store', type='string',
                      dest='worker_comment',
                      default='',
                      help='optional text to describe worker configuration')

    parser.add_option('--build', action='store_true',
                      default=False, help='Perform own builds')

    parser.add_option('--debugger', action='store', type='string',
                      dest='debugger',
                      default=None,
                      help='Add --debugger=value to environment variable EXTRA_TEST_ARGS ' +
                      'Defaults to None.')

    parser.add_option('--debugger-args', action='store', type='string',
                      dest='debugger_args',
                      default=None,
                      help='Add --debugger-args=value to environment variable EXTRA_TEST_ARGS. ' +
                      'Defaults to None.')

    parser.add_option('--global-timeout', action='store', type='int',
                      dest='global_timeout',
                      default=3,
                      help='Terminate the test if it runs longer than value hours. ' +
                      'Defaults to 3.')

    parser.add_option('--test-timeout', action='store', type='int',
                      dest='test_timeout',
                      default=None,
                      help='Add --timeout=value to environment variable EXTRA_TEST_ARGS. ' +
                      'This is the per test timeout in seconds for the tests. ' +
                      'Defaults to None.')

    parser.add_option('--all-test-results', action='store_true',
                      dest='all_test_results',
                      help='By default only record unexpected unittest results. ' +
                      'Add --all-test-results to record all results.')

    parser.add_option('--nodebug', action='store_false', 
                      dest='debug',
                      default=False,
                      help='default - no debug messages')

    parser.add_option('--debug', action='store_true', 
                      dest='debug',
                      help='turn on debug messages')

    (options, args) = parser.parse_args()

    if options.debugger_args and not options.debugger:
         parser.print_help()
         exit(1)

    if options.couchserveruri is None:
         parser.print_help()
         exit(1)

    exception_counter = 0

    this_worker     = UnitTestWorker(startdir, programPath, options.couchserveruri, options.databasename, options.worker_comment, options.debug)

    programModTime = os.stat(programPath)[stat.ST_MTIME]

    this_worker.logMessage('starting worker %s %s %s with program dated %s' %
                          (this_worker.document['os_name'], this_worker.document['os_version'], this_worker.document['cpu_name'],
                           time.ctime(programModTime)))
    while True:
        try:
            this_worker.doWork()
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except:
            exception_counter += 1
            if exception_counter > 100:
                print "Too many errors. Terminating."
                break

            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

            if re.search('KeyboardInterrupt', errorMessage):
                raise KeyboardInterrupt

            if str(exceptionValue) == 'WorkerInconsistent':
                # If we were disabled, sleep for 5 minutes and check our state again.
                # otherwise restart.
                if this_worker.document["state"] == "disabled":
                    while True:
                        time.sleep(300)
                        curr_worker_doc = this_worker.testdb.getDocument(this_worker.document["_id"])
                        if not curr_worker_doc:
                            # we were deleted. just terminate
                            exit(2)
                        if curr_worker_doc["state"] != "disabled":
                            this_worker.document["state"] = "undisabled"
                            break

            this_worker.logMessage('main: exception %s: %s' % (str(exceptionValue), sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)))

            time.sleep(60)


if __name__ == "__main__":
    try:
        restart = True
        main()
    except KeyboardInterrupt:
        restart = False
    except SystemExit:
        restart = False
    except:
        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
        print 'main: exception %s: %s' % (str(exceptionValue), sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback))

    # kill any test processes still running.
    if this_worker:
        this_worker.killTest()

    if this_worker is None:
        exit(2)

    if restart:
        # continue trying to log message until it succeeds.
        while True:
            try:
                this_worker.logMessage('Program restarting', True)
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                print 'main: exception: %s, %s' % (exceptionValue, errorMessage)
        this_worker.reloadProgram()
    else:
        this_worker.logMessage('Program terminating', False)
        this_worker.testdb.deleteDocument(this_worker.document, False)


