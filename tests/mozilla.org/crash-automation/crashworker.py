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
sys.path.append(os.path.join(sisyphus_dir, 'bin'))

import sisyphus.utils
import sisyphus.couchdb
import sisyphus.builder
import sisyphus.worker

startdir       = os.getcwd()
programPath = os.path.abspath(os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])), os.path.basename(sys.argv[0])))

options          = None

os.chdir(sisyphus_dir)
os.environ["TEST_TOPSITE_TIMEOUT"]="300"
os.environ["TEST_TOPSITE_PAGE_TIMEOUT"]="120"
os.environ["XPCOM_DEBUG_BREAK"]="warn"

stackwalkPath = os.environ.get('MINIDUMP_STACKWALK', "/usr/local/bin/minidump_stackwalk")

class CrashTestWorker(sisyphus.worker.Worker):

    def __init__(self, startdir, programPath, testdb, historydb, worker_comment, branches, debug):
        sisyphus.worker.Worker.__init__(self, startdir, programPath, testdb, historydb, worker_comment, branches, debug)
        self.signature_doc = None
        self.document['signature_id'] = None
        self.updateWorker(self.document)

        # Workers obtain signatures to process by retrieving them from
        # the pending jobs view. They potentially search the queue
        # multiple times as they attempt to find the best matching
        # signatures based on priority, operating system, cpu type and
        # operating system version. As signatures are processed by the
        # not best matching workers, they collect at the beginning of
        # the job queue until such time as the best matching workers
        # process and delete them. We can alleviate the problem of
        # workers continually searching through already processed
        # signatures by keeping track of the number of signatures in
        # each queue already processed by a worker and skipping over
        # them. It is not possible to keep track of the already
        # processed signatures that are later deleted by the best
        # matching worker for the signature, therefore the counts of
        # signatures to be skipped are reset periodically.

        # jobviewdata is an array with an entry for each possible
        # priority. Each of the items in the jobviewdata array is an
        # array of viewdata items. viewdata items contain the start
        # and end keys and a skip value to be used when querying the
        # pending jobs queue. Note that a skip value is set to -1 when
        # a search of the pending jobs returns zero signatures. It is
        # used to prevent the worker from wasting time trying to query
        # the pending jobs with that set of keys since there are no
        # matching signatures.
        self.jobviewdata = []

        # jobviewdata_datetime is the timestamp of the last time the
        # job queues' skip values where reset. It is used to determine
        # when to reset the values again.
        self.jobviewdata_datetime = datetime.datetime.now()

        # viewdata is a temporary field used to record the currently
        # active viewdata item.
        self.viewdata    = None

        for priority in 0, 1:
            self.jobviewdata.append([])

            fullkey = [str(priority),
                       self.document["os_name"],
                       self.document["cpu_name"],
                       self.document["os_version"]]

            key = fullkey

            while len(key) > 0:
                viewdata = {
                    'skip'     : 0,
                    'startkey' : list(key),
                    'endkey'   : list(key)
                    }
                viewdata['endkey'][len(key)-1] += '\u9999'
                self.jobviewdata[priority].append(viewdata)
                del key[len(key)-1]


    def checkForUpdate(self):
        if os.stat(self.programPath)[stat.ST_MTIME] != self.programModTime:
            message = 'checkForUpdate: Program change detected. Reloading from disk. %s %s' % (sys.executable, sys.argv)
            self.logMessage(message)
            if self.document is not None:
                try:
                    self.document['state'] = message
                    if self.document["signature_id"]:
                        signature_doc = self.testdb.getDocument(self.document["signature_id"])
                        if signature_doc:
                            if self.document["_id"] == signature_doc["worker"]:
                                signature_doc["worker"] = None
                                self.testdb.updateDocument(signature_doc)
                            else:
                                self.debugMessage("checkForUpdate: worker's linked signature %s belongs to %s" % (self.document["signature_id"], signature_doc["worker"]))
                        else:
                            self.debugMessage("checkForUpdate: worker's linked signature %s is deleted" % self.document["signature_id"])
                    self.updateWorker(self.document)
                except:
                    pass
            sys.stdout.flush()
            newargv = sys.argv
            newargv.insert(0, sys.executable)
            os.chdir(self.startdir)
            os.execvp(sys.executable, newargv)

    def amIOk(self):
        """
        check our worker document against the database's version
        to make sure we are in sync, that the signature relationship is intact,
        and to see if we have been zombied or disabled.
        """
        if not self.document:
            # don't check out state if we haven't been initialized.
            return

        consistent         = True
        worker_id          = self.document["_id"]
        worker_state       = self.document["state"]
        signature_id       = self.document["signature_id"]

        try:
            curr_worker_doc = self.testdb.getDocument(worker_id)

            if not curr_worker_doc:
                # someone deleted our worker document in the database!
                self.logMessage("amIOk: worker %s was deleted by someone else." % worker_id)
                if signature_id:
                    curr_signature_doc = self.testdb.getDocument(signature_id)
                    if not curr_signature_doc or worker_id != curr_signature_doc["worker"]:
                        self.logMessage("amIOk: our signature document %s was deleted or is no longer owned by us: %s." % (signature_id, curr_signature_doc))
                        self.document["signature_id"] = None
                        consistent = False
                # XXX: do we need to change or remove the _rev property before re-inserting?
                self.testdb.createDocument(self.document)

            if self.document["_rev"] == curr_worker_doc["_rev"]:
                # our revisions match, so the database and the local
                # copy of our worker are in sync. Our signature doc
                # should exist and should point back to us.
                if signature_id:
                    curr_signature_doc = self.testdb.getDocument(signature_id)
                    if not curr_signature_doc:
                        self.logMessage("amIOk: worker %s's signature %s was deleted by someone else." % (worker_id, signature_id))
                        self.document["signature_id"] = None
                        self.document["state"] = "signature error"
                        self.testdb.updateDocument(self.document, True)
                        consistent = False
                    elif worker_id != curr_signature_doc["worker"]:
                        self.logMessage("amIOk: worker %s's signature %s was stolen by %s" % (worker_id, signature_id, curr_signature_doc["worker"]))
                        self.document["signature_id"] = None
                        self.document["state"] = "signature error"
                        self.testdb.updateDocument(self.document, True)
                        consistent = False
            else:
                # our revisions differ, so someone else has updated
                # our worker document in the database. They could have
                # disabled us or zombied us and taken away our signature
                # or undisabled us.

                self.document["_rev"] = curr_worker_doc["_rev"]
                curr_worker_state       = curr_worker_doc["state"]

                if worker_state != "disabled" and curr_worker_state == "disabled":
                    # we were disabled. free our signature if necessary.
                    self.document["state"] = "disabled"
                    consistent               = False

                    self.logMessage("amIOk: worker %s was disabled." % worker_id)

                    if signature_id:
                        curr_signature_doc = self.testdb.getDocument(signature_id)
                        if curr_signature_doc and worker_id == curr_signature_doc["worker"]:
                            self.logMessage("amIOk: worker %s freeing signature %s.." % (worker_id, signature_id))
                            curr_signature_doc["worker"] = None
                            self.testdb.updateDocument(curr_signature_doc, True)
                        self.document["signature_id"] = None
                        self.testdb.updateDocument(self.document, True)
                elif worker_state != "zombie" and curr_worker_state == "zombie":
                    # we were zombied but are not dead!
                    self.document["state"] = "undead"
                    consistent               = False

                    self.logMessage("amIOk: worker %s was zombied but is not dead." % worker_id)

                    if signature_id:
                        # when zombied, our signature should have been taken away.
                        curr_signature_doc = self.testdb.getDocument(signature_id)
                        if curr_signature_doc and worker_id == curr_signature_doc["worker"]:
                            self.logMessage("amIOk: worker %s freeing signature %s.." % (worker_id, signature_id))
                            curr_signature_doc["worker"] = None
                            self.testdb.updateDocument(curr_signature_doc, True)
                        self.document["signature_id"] = None
                        self.testdb.updateDocument(self.document, True)
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.logMessage('amIOk: worker: %s, exception: %s' % (worker_id, errorMessage))
            raise

        if not consistent:
            raise Exception('WorkerInconsistent')

    def killZombies(self):
        """ zombify any *other* worker who has not updated status in zombie_time hours"""

        now          = datetime.datetime.now()
        deadinterval = datetime.timedelta(hours=self.zombie_time)
        worker_rows  = self.getAllWorkers()
        this_worker_id = self.document['_id']

        for worker_row in worker_rows:
            worker_row_id = worker_row['_id']

            if worker_row_id == self.document['_id']:
                # don't zombify ourselves
                continue

            if worker_row['state'] == 'disabled' or worker_row['state'] == 'zombie':
                # don't zombify disabled or zombified workers
                continue

            timestamp = sisyphus.utils.convertTimestamp(worker_row['datetime'])

            if now - timestamp > deadinterval:
                self.logMessage("killZombies: worker %s zombifying %s (%s)" % (this_worker_id, worker_row_id, worker_row['datetime']))
                worker_row["state"] = "zombie"
                signature_id = worker_row['signature_id']
                if signature_id:
                    worker_row['signature_id'] = None
                    signature_doc = self.testdb.getDocument(signature_id)
                    if signature_doc and worker_row_id == signature_doc['worker'] :
                        self.logMessage("killZombies: worker %s freeing zombie %s's signature %s.." % (this_worker_id, worker_row_id, signature_id))
                        signature_doc['worker'] = None
                        self.testdb.updateDocument(signature_doc)
                self.updateWorker(worker_row)

    def runTest(self, product, branch, buildtype, url, url_index, extra_test_args):

        # encode the url
        url            = sisyphus.utils.makeUnicodeString(url)
        urlParseObject = urlparse.urlparse(url)
        urlPieces      = [urllib.quote(urlpiece, "/=:") for urlpiece in urlParseObject]
        url            = urlparse.urlunparse(urlPieces)

        timestamp = sisyphus.utils.getTimestamp()

        result_doc = {
            "_id"               : "%s_result_%05d_%s" % (self.signature_doc["_id"], url_index, self.document['_id']),
            "type"              : "result",
            "product"           : product,
            "branch"            : branch,
            "buildtype"         : buildtype,
            "os_name"           : self.document["os_name"],
            "os_version"        : self.document["os_version"],
            "cpu_name"          : self.document["cpu_name"],
            "worker_id"         : self.document["_id"],
            "changeset"         : self.document[branch]["changeset"],
            "datetime"          : timestamp,
            "url"               : url,
            "major_version"     : self.signature_doc["major_version"],
            "signature"         : self.signature_doc["signature"],
            "bug_list"          : self.signature_doc["bug_list"],
            "os_versionhash"    : self.signature_doc["os_versionhash"],
            "versionhash"       : self.signature_doc["versionhash"],
            "major_versionhash" : self.signature_doc["major_versionhash"],
            "ASSERTIONS"        : {},
            "reproduced"        : False,
            "test"              : "crashtest",
            "extra_test_args"   : None,
            }

        self.testdb.createDocument(result_doc)

        page               = "head"
        executablepath     = ""
        profilename        = ""
        reExecutablePath   = re.compile(r'environment: TEST_EXECUTABLEPATH=(.*)')
        reProfileName      = re.compile(r'environment: TEST_PROFILENAME=(.*)')
        reAssertionFail    = re.compile(r'Assertion fail.*')
        reASSERTION        = re.compile(r'.*ASSERTION: (.*), file (.*), line [0-9]+.*')
        reValgrindLeader   = re.compile(r'==[0-9]+==')
        reSpiderBegin      = re.compile(r'Spider: Begin loading (.*)')
        reUrlExitStatus    = re.compile(r'(http.*): EXIT STATUS: (.*) [(].*[)].*')
        reExploitableClass = re.compile(r'^Exploitability Classification: (.*)')
        reExploitableTitle = re.compile(r'^Recommended Bug Title: (.*)')

        # buffers to hold assertions and valgrind messages until
        # a test result is seen in the output.
        assertion_list = []
        valgrind_text  = ""

        data    = u""

        proc = subprocess.Popen(
            [
                "./bin/tester.sh",
                "-t",
                "tests/mozilla.org/top-sites/test.sh -u " +
                url +
                " -D 1 -h http://test.mozilla.com/tests/mozilla.org/crash-automation/userhook-crash.js",
                product,
                branch,
                buildtype
                ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        stdout, stderr = proc.communicate()

        logfilename = re.search('log: (.*\.log) ', stdout).group(1)

        logfile = open(logfilename, "r")

        while 1:
            line = logfile.readline()
            if not line:
                break

            # decode to unicode
            line = sisyphus.utils.makeUnicodeString(line)

            data += line

            if not executablepath:
                match = reExecutablePath.match(line)
                if match:
                    executablepath = match.group(1)

            if not profilename:
                match = reProfileName.match(line)
                if match:
                    profilename = match.group(1)

            # dump assertions and valgrind messages whenever we see a
            # new page being loaded.
            match = reSpiderBegin.match(line)
            if match:
                self.process_assertions(result_doc["_id"], product, branch, buildtype, timestamp, assertion_list, page, "crashtest", extra_test_args)
                valgrind_list = self.parse_valgrind(valgrind_text)
                self.process_valgrind(result_doc["_id"], product, branch, buildtype, timestamp, valgrind_list, page, "crashtest", extra_test_args)

                assertion_list   = []
                valgrind_text    = ""
                page = match.group(1).strip()

            if self.document["os_name"] == "Windows NT":
                match = reExploitableClass.match(line)
                if match:
                    result_doc["exploitableclass"] = match.group(1)
                match = reExploitableTitle.match(line)
                if match:
                    result_doc["exploitabletitle"] = match.group(1)

            match = reAssertionFail.match(line)
            if match:
                result_doc["assertionfail"] = match.group(0)

            match = reASSERTION.match(line)
            if match:
                # record the assertion for later output when we know the test
                assertion_list.append({
                        "message" : match.group(1),
                        "file"    : match.group(2),
                        "datetime" : timestamp,
                        })
                # count the ASSERTIONS
                if not match.group(1) in result_doc["ASSERTIONS"]:
                    result_doc["ASSERTIONS"][match.group(1)] = 0
                result_doc["ASSERTIONS"][match.group(1)] += 1

            match = reValgrindLeader.match(line)
            if match:
                valgrind_text += line

            match = reUrlExitStatus.match(line)
            if match:
                result_doc["exitstatus"]       = match.group(2)
                if re.search('(CRASHED|ABNORMAL)', result_doc["exitstatus"]):
                    result_doc["reproduced"] = True
                else:
                    result_doc["reproduced"] = False

        logfile.close()
        if not result_doc["reproduced"]:
            os.unlink(logfilename)

        result_doc = self.testdb.saveAttachment(result_doc, 'log', data, 'text/plain', True, True)

        symbolsPath = os.path.join(executablepath, 'crashreporter-symbols')

        self.debugMessage("stackwalkPath: %s, symbolsPath: %s, exists: %s" % (stackwalkPath, symbolsPath, os.path.exists(symbolsPath)))

        if stackwalkPath and os.path.exists(stackwalkPath) and os.path.exists(symbolsPath):
            dumpFiles = glob.glob(os.path.join('/tmp/' + profilename + '/minidumps', '*.dmp'))
            self.debugMessage("dumpFiles: %s" % (dumpFiles))
            if len(dumpFiles) > 0:
                self.logMessage("runTest: %s: %d dumpfiles found in /tmp/%s" % (url, len(dumpFiles), profilename))

            for dumpFile in dumpFiles:
                self.logMessage("runTest: processing dump: %s" % (dumpFile))
                # use timed_run.py to run stackwalker since it can hang on
                # win2k3 at least...
                self.debugMessage("/usr/bin/python " + sisyphus_dir + "/bin/timed_run.py")
                try:
                    proc = subprocess.Popen(
                        [
                            "python",
                            sisyphus_dir + "/bin/timed_run.py",
                            "300",
                            "-",
                            stackwalkPath,
                            dumpFile,
                            symbolsPath
                            ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
                    stdout, stderr = proc.communicate()
                    self.debugMessage("stackwalking: stdout: %s" % (stdout))
                    self.debugMessage("stackwalking: stderr: %s" % (stderr))

                    result_doc = self.testdb.saveAttachment(result_doc, 'crashreport', stdout, 'text/plain', True, True)
                except:
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                    self.logMessage('runTest: exception processing dump: %s, %s' % (exceptionValue, errorMessage))

                result_doc["reproduced"] = True

                crash_data = self.parse_crashreport(stdout)
                self.process_crashreport(result_doc["_id"], product, branch, buildtype, timestamp, crash_data, page, "crashtest", extra_test_args)

                data = ''
                extraFile = dumpFile.replace('.dmp', '.extra')
                try:
                    extraFileHandle = open(extraFile, 'r')
                    for extraline in extraFileHandle:
                        data += extraline
                    result_doc = self.testdb.saveAttachment(result_doc, 'extra', data, 'text/plain', True, True)
                except:
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                    self.logMessage('runTest: exception processing extra: %s, %s' % (exceptionValue, errorMessage))

                finally:
                    try:
                        extraFileHandle.close()
                    except:
                        pass
                # Ignore multiple dumps
                break

        self.testdb.updateDocument(result_doc)

        if result_doc['reproduced'] and re.search('\d{8}_', self.signature_doc['_id']):

            # for reproduced results whose original signature
            # documents match the normal id pattern starting with a
            # CCYYMMDD_ date, issue new signature documents with
            # automatically generated ids for the url for each major
            # version for the other os_name, cpu_name, os_version
            # combinations available for testing.

            try:
                worker_rows = self.getAllWorkers()
                build_data  = getBuildData(self.testdb)

                for worker_doc in worker_rows:
                    # Skip other workers who match us exactly but do reissue a
                    # signature for us so that we can test if the crash is also
                    # reproducible on the same machine where it originally occured.
                    if (worker_doc['_id']        != self.document['_id'] and
                        worker_doc['os_name']    == self.document['os_name'] and
                        worker_doc['cpu_name']   == self.document['cpu_name'] and
                        worker_doc['os_version'] == self.document['os_version']):
                        continue

                    for major_version in build_data:

                        new_signature_doc = dict(self.signature_doc)
                        del new_signature_doc['_id']
                        del new_signature_doc['_rev']

                        for field in 'os_name', 'cpu_name', 'os_version':
                            new_signature_doc[field] = worker_doc[field]

                        new_signature_doc['major_version'] = major_version
                        new_signature_doc['priority']      = '0'
                        new_signature_doc['processed_by']  = {}
                        new_signature_doc['urls']          = [page]
                        new_signature_doc['worker']        = None

                        self.testdb.createDocument(new_signature_doc)
                        self.debugMessage('runTest: adding reproducer signature document: %s' % new_signature_doc)

            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                self.testdb.logMessage('runTest: unable to duplicate signature %s for reproduction: %s' % (self.signature_doc, errorMessage))

        # process any remaining assertion or valgrind messages.
        self.process_assertions(result_doc["_id"], product, branch, buildtype, timestamp, assertion_list, page, "crashtest", extra_test_args)
        valgrind_list = self.parse_valgrind(valgrind_text)
        self.process_valgrind(result_doc["_id"], product, branch, buildtype, timestamp, valgrind_list, page, "crashtest", extra_test_args)

    def getMatchingWorkerIds(self, startkey=None, endkey=None):

        matching_worker_rows = self.getRows(self.testdb.db.views.default.matching_workers, startkey, endkey)
        return matching_worker_rows

    def checkIfUrlAlreadyTested(self, signature_doc, url_index):

        startkey = "%s_result_%05d_%s" % (signature_doc["_id"], url_index, self.document['_id'])
        endkey   = "%s_result_%05d\u9999" % (signature_doc["_id"], url_index);
        result_rows = self.getRows(self.testdb.db.views.default.results_all, startkey, endkey)
        self.debugMessage('checkIfUrlAlreadyTested: %s' % (len(result_rows) != 0))

        # only count already tested if this worker has tested the url.
        # the isBetterAvailable algorithm will have prevented different
        # though equivalent workers from calling checkIfUrlAlreadyTested.
        for result in result_rows:
            if self.document['_id'] == result['worker_id']:
                self.debugMessage('checkIfUrlAlreadyTested: True')
                return True

        self.debugMessage('checkIfUrlAlreadyTested: False')
        return False

    def getPendingJobs(self, startkey=None, endkey=None, skip=None, limit=1000000):

        if skip is None:
            skip = 0

        for attempt in self.testdb.max_db_attempts:
            try:
                pending_job_rows = self.testdb.db.views.default.pending_jobs(startkey=startkey, endkey=endkey, skip=skip, limit=limit)
                self.debugMessage('getPendingJobs: startkey: %s, endkey: %s, matches: %d' % (startkey, endkey, len(pending_job_rows)))
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                # reconnect to the database in case it has dropped
                self.testdb.connectToDatabase(None)
                self.logMessage('getPendingJobs: attempt: %d, startkey: %s, endkey: %s, exception: %s' %
                                (attempt, startkey, endkey, errorMessage))
                self.amIOk()

            if attempt == self.testdb.max_db_attempts[-1]:
                raise Exception("getPendingJobs: aborting after %d attempts" % (self.testdb.max_db_attempts[-1] + 1))
            time.sleep(60)

        if attempt > 0:
            self.logMessage('getPendingJobs: attempt: %d, success' % (attempt))

        self.debugMessage('getPendingJobs: startkey=%s, endkey=%s, count: %d' % (startkey, endkey, len(pending_job_rows)))

        return pending_job_rows

    def getAllJobs(self):

        job_rows = self.getRows(self.testdb.db.views.default.jobs_by_worker)

        return job_rows

    def isBetterWorkerAvailable(self, signature_doc):

        self.debugMessage('isBetterWorkerAvailable: checking signature %s' % signature_doc['_id'])

        # try for an exact  match on the signature's os_name, os_version, cpu_name
        # exact matches are by definition the best.
        startkey = [signature_doc["os_name"], signature_doc["os_version"], signature_doc["cpu_name"]]
        endkey   = [signature_doc["os_name"], signature_doc["os_version"], signature_doc["cpu_name"] + "\u9999"]

        matching_worker_id_rows = self.getMatchingWorkerIds(startkey=startkey, endkey=endkey)

        self.debugMessage('isBetterWorkerAvailable: startkey: %s, endkey=%s, matching workers: %s' % (startkey, endkey, len(matching_worker_id_rows)))

        if len(matching_worker_id_rows) > 0:
            # workers are an exact match on os_name, os_version, cpu_name
            for matching_worker_id_doc in matching_worker_id_rows:
                self.debugMessage("isBetterWorkerAvailable: checking worker %s" % matching_worker_id_doc["worker_id"])
                if self.document["_id"] == matching_worker_id_doc["worker_id"]:
                    # this worker is the best available
                    self.debugMessage("isBetterWorkerAvailable: False. this worker %s is the best available." % self.document["_id"])
                    return False
                if matching_worker_id_doc["worker_id"] in signature_doc["processed_by"]:
                    # the worker already processed the signature and was the best.
                    self.debugMessage("isBetterWorkerAvailable: False. worker %s already processed signature and was the best available." % matching_worker_id_doc["worker_id"])
                    return False
                self.debugMessage("isBetterWorkerAvailable: True. worker %s has not processed signature and is the best available." % matching_worker_id_doc["worker_id"])
            return True


        # try a match on the signature's os_name, os_version
        startkey = [signature_doc["os_name"], signature_doc["os_version"]]
        endkey   = [signature_doc["os_name"], signature_doc["os_version"] + "\u9999"]

        matching_worker_id_rows = self.getMatchingWorkerIds(startkey=startkey, endkey=endkey)

        self.debugMessage('isBetterWorkerAvailable: startkey: %s, endkey=%s, matching workers: %s' % (startkey, endkey, len(matching_worker_id_rows)))

        if len(matching_worker_id_rows) > 0:
            # workers are an exact match on os_name, os_version
            for matching_worker_id_doc in matching_worker_id_rows:
                self.debugMessage("isBetterWorkerAvailable: checking worker %s" % matching_worker_id_doc["worker_id"])
                if self.document["_id"] == matching_worker_id_doc["worker_id"]:
                    # this worker is the best available
                    self.debugMessage("isBetterWorkerAvailable: False. this worker %s is the best available." % self.document["_id"])
                    return False
                if matching_worker_id_doc["worker_id"] in signature_doc["processed_by"]:
                    self.debugMessage("isBetterWorkerAvailable: False. worker %s already processed signature and was the best available." % matching_worker_id_doc["worker_id"])
                    # the worker already processed the signature and was the best.
                    return False
                self.debugMessage("isBetterWorkerAvailable: True. worker %s has not processed signature and is the best available." % matching_worker_id_doc["worker_id"])
            return True

        # try a match on the signature's os_name
        startkey = [signature_doc["os_name"]]
        endkey   = [signature_doc["os_name"] + "\u9999"]

        matching_worker_id_rows = self.getMatchingWorkerIds(startkey=startkey, endkey=endkey)

        self.debugMessage('isBetterWorkerAvailable: startkey: %s, endkey=%s, matching workers: %s' % (startkey, endkey, len(matching_worker_id_rows)))

        if len(matching_worker_id_rows) > 0:
            # workers are an exact match on os_name
            for matching_worker_id_doc in matching_worker_id_rows:
                self.debugMessage("isBetterWorkerAvailable: checking worker %s" % matching_worker_id_doc["worker_id"])
                if self.document["_id"] == matching_worker_id_doc["worker_id"]:
                    # this worker is the best available
                    self.debugMessage("isBetterWorkerAvailable: False. this worker %s is the best available." % self.document["_id"])
                    return False
                if matching_worker_id_doc["worker_id"] in signature_doc["processed_by"]:
                    # the worker already processed the signature and was the best.
                    self.debugMessage("isBetterWorkerAvailable: False. worker %s already processed signature and was the best available." % matching_worker_id_doc["worker_id"])
                    return False
                self.debugMessage("isBetterWorkerAvailable: True. worker %s has not processed signature and is the best available." % matching_worker_id_doc["worker_id"])
            return True

        # no matches for os. allow each worker type a chance.
        # return True if there is a worker different from us
        # which differs in operating system, operating system version
        # or cpu type which has not yet processed the signature.
        #
        # this will cover the null signature/null os crash reports.

        self.debugMessage('isBetterWorkerAvailable: checking all workers')

        worker_rows = self.getAllWorkers()

        for worker_doc in worker_rows:
            self.debugMessage("isBetterWorkerAvailable: checking worker %s" % worker_doc["_id"])
            if (self.document["_id"] != worker_doc["_id"] and
                worker_doc["_id"] not in signature_doc["processed_by"]):
                if (self.document["os_name"] != worker_doc["os_name"] or
                    self.document["os_version"] != worker_doc["os_version"] or
                    self.document["cpu_name"] != worker_doc["cpu_name"]):
                    return True

        return False

    def freeOrphanJobs(self):

        signature_rows = self.getAllJobs()

        for signature_doc in signature_rows:
            worker_id    = signature_doc["worker"]
            signature_id = signature_doc["_id"]

            worker_doc = self.testdb.getDocument(worker_id)
            if not worker_doc:
                self.debugMessage("freeOrphanJobs: job %s's worker %s is deleted." % (signature_id, worker_id))
                signature_doc["worker"] = None
                self.testdb.updateDocument(signature_doc)
            elif signature_id != worker_doc["signature_id"]:
                # double check that the signature has not changed it's worker
                temp_signature_doc = self.testdb.getDocument(signature_id)
                if not temp_signature_doc:
                    self.debugMessage("freeOrphanJobs: ignoring race condition: signature %s was deleted" % signature_id)
                elif temp_signature_doc["worker"] != worker_id:
                    self.debugMessage("freeOrphanJobs: ignoring race condition: signature %s's worker changed from %s to %s" %
                                      (signature_id,  worker_id, temp_signature_doc["worker"]))
                else:
                    self.debugMessage("freeOrphanJobs: job %s's worker %s is working on %s." % (signature_id, worker_id, worker_doc["signature_id"]))
                    signature_doc["worker"] = None
                    self.testdb.updateDocument(signature_doc)

    def checkSignatureForWorker(self, pending_job_rows):
        """
        Return a signature document from the pending_job_rows list
        which has not been processed by this worker while updating
        the signature document and this worker to show the worker
        is processing the signature.

        Any signatures which this worker has already processed and
        for which there are no better matching workers than the current
        worker are deleted.

        Update and delete conflicts on signatures cause the signature to be
        ignored (as being taken by other workers).
        """

        self.debugMessage("checkSignatureForWorker: checking %d pending jobs" % len(pending_job_rows))

        for pending_job in pending_job_rows:
            try:
                signature_id  = pending_job["signature_id"]
                self.debugMessage("checkSignatureForWorker: checking signature %s" % signature_id)
                signature_doc = self.testdb.getDocument(signature_id)
                if not signature_doc or signature_doc["worker"]:
                    self.debugMessage("checkSignatureForWorker: race condition: someone else got the signature document %s" % signature_id)
                    continue
            except:
                raise

            self.debugMessage("checkSignatureForWorker: check if we have processed signature %s" % signature_id)

            if self.document["_id"] in signature_doc["processed_by"]:

                self.debugMessage("checkSignatureForWorker: we already processed signature %s" % signature_id)

                # We have already processed this signature document. Increment the skip value
                # so we don't keep processing it.
                self.viewdata['skip'] += 1

                # Depending on the population of workers, we were not
                # the best at the time we originally processed the
                # signature, but if we are the best now, we can go
                # ahead and delete it and try for the next job
                if not self.isBetterWorkerAvailable(signature_doc):
                    self.debugMessage("checkSignatureForWorker: there is not a better worker available, deleting signature %s" % signature_id)
                    self.testdb.deleteDocument(signature_doc)
                    self.viewdata['skip'] -= 1
                    if self.viewdata['skip'] < 0:
                        self.viewdata['skip'] = 0
                continue

            self.debugMessage("checkSignatureForWorker: returning signature %s" % signature_doc["_id"])

            # update the signature and this worker
            # signature_doc["worker"] <-> self.document["_id"].

            self.debugMessage("checkSignatureForWorker: update signature %s's worker" % signature_id)
            signature_doc["worker"] = self.document["_id"]
            self.testdb.updateDocument(signature_doc)

            self.debugMessage("checkSignatureForWorker: update worker %s's signature" % self.document["_id"])
            try:
                self.document["signature_id"] = signature_id
                self.updateWorker(self.document)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                self.logMessage("checkSignatureForWorker: exception %s updating worker: %s" % (exceptionValue, errorMessage))
                # update signature to remove the worker. allow any exception to be raised to the caller.
                signature_doc["worker"] = self.document["_id"]
                self.testdb.updateDocument(signature_doc)
                raise

            return signature_doc

        self.debugMessage("checkSignatureForWorker: returning signature None")

        return None


    def getSignatureForWorker(self):
        """
        return a signature unprocessed by this worker
        matches on priority, os_name, cpu_name, os_version
        or a subset of those properties by relaxing the right
        most condition until a match is found.
        """

        limit         = 5
        signature_doc = None

        lock_pending_jobs = {'type'  : 'lock',
                             '_id'   : 'lock_pending_jobs',
                             'owner' : self.document['_id']}

        if not self.testdb.createLock(lock_pending_jobs):
            self.debugMessage("getSignatureForWorker: unable to obtain lock_pending_jobs.")
            return signature_doc

        try:

            resetskip_interval = datetime.timedelta(hours=1)
            if datetime.datetime.now() - self.jobviewdata_datetime > resetskip_interval:
                # Periodically reset the viewdata for each queue in
                # case priorities have changed, new signatures have
                # been added, or to handle the case where other
                # workers have deleted our already processed
                # signatures.
                self.jobviewdata_datetime = datetime.datetime.now()
                for prioritydata in self.jobviewdata:
                    for viewdata in prioritydata:
                        viewdata['skip'] = 0

            for prioritydata in self.jobviewdata:
                for self.viewdata in prioritydata:

                    self.debugMessage("getSignatureForWorker: key: %s, skip: %d" % (self.viewdata['startkey'], self.viewdata['skip']))

                    if self.viewdata['skip'] < 0:
                        continue

                    job_rows = self.getPendingJobs(startkey = self.viewdata['startkey'],
                                                   endkey   = self.viewdata['endkey'],
                                                   skip     = self.viewdata['skip'],
                                                   limit    = limit)
                    if len(job_rows) == 0:
                        self.viewdata['skip'] = -1
                        continue

                    signature_doc    = self.checkSignatureForWorker(job_rows)
                    if signature_doc:
                        break

                if signature_doc:
                    break

        except:
            self.testdb.deleteLock(lock_pending_jobs)
            raise

        self.testdb.deleteLock(lock_pending_jobs)

        if signature_doc:
            pass
        elif len(job_rows) == 0:
            self.debugMessage('getSignatureForWorker: skipped past the end of the pending jobs.')
            self.viewdata = None
            for prioritydata in self.jobviewdata:
                for viewdata in prioritydata:
                    viewdata['skip'] = 0
            time.sleep(300)

        self.debugMessage("getSignatureForWorker: returning signature %s" % signature_doc)

        return signature_doc

    def doWork(self):

        waittime = 0

        checkup_interval = datetime.timedelta(minutes=5)
        last_checkup_time = datetime.datetime.now() - 2*checkup_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate()
                self.testdb.checkDatabase()
                self.historydb.checkDatabase()
                self.killZombies()
                self.freeOrphanJobs()
                last_checkup_time = datetime.datetime.now()

            sys.stdout.flush()
            time.sleep(waittime)
            waittime = 0

            if not self.signature_doc:
                # check and clean up lock file if necessary.
                lock_pending_jobs = self.testdb.getDocument('lock_pending_jobs')
                if lock_pending_jobs and lock_pending_jobs['owner'] == self.document['_id']:
                    self.logMessage("doWork: deleting stale lock_pending_jobs")
                    self.testdb.deleteLock(lock_pending_jobs)

                self.signature_doc = self.getSignatureForWorker()
                if self.signature_doc:
                    if self.document["state"] == "idle":
                        self.debugMessage('New signatures available to process, going active.')

                    url_index     = 0
                    major_version = self.signature_doc["major_version"]
                    build_data    = getBuildData(self.testdb)
                    branch_data   = build_data[major_version]
                    if not branch_data:
                        raise Exception("unsupported version: %s" %(major_version))

                    branch    = branch_data["branch"]
                    buildtype = "debug"

                else:
                    url_index     = -1
                    major_version = None
                    branch_data   = None
                    branch        = None
                    buildtype     = None
                    waittime      = 1

                    if self.document["state"] != "idle":
                        self.debugMessage('No signatures available to process, going idle.')

                    # XXX: right now we may need to update here to keep the worker alive
                    # but when we have a worker heartbeat thread we can move these
                    # updates to under the conditional above.
                    self.document["state"]    = "idle"
                    self.document["datetime"] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)

            elif (not self.document[branch]["builddate"] or
                  sisyphus.utils.convertTimestamp(self.document[branch]["builddate"]).day != datetime.date.today().day):

                self.update_bug_histories()

                buildstatus =  self.buildProduct("firefox", branch, buildtype)

                if not buildstatus["success"]:
                    # wait for five minutes if a build failure occurs
                    waittime = 300
                    # release the signature
                    self.signature_doc["worker"]  = None
                    self.testdb.updateDocument(self.signature_doc, True)
                    self.signature_doc = None
                    self.clobberProduct("firefox", branch, buildtype)

            elif (self.document[branch]["builddate"] and url_index < len(self.signature_doc["urls"])):

                url = self.signature_doc["urls"][url_index]

                if not self.checkIfUrlAlreadyTested(self.signature_doc, url_index):
                    self.debugMessage("testing firefox %s %s %s" % (branch, buildtype, url))
                    self.document["state"]        = "testing firefox %s %s %s" % (branch, buildtype, url)
                    self.document["datetime"]     = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    try:
                        # XXX: extra_test_args should be something to pass parameters to the
                        # test process.
                        extra_test_args = None
                        self.runTest("firefox", branch, buildtype, url, url_index, extra_test_args)
                        # if the signature was null, process all urls.
                        #if result["reproduced"] and self.signature_doc["signature"] != "\\N":
                        #    url_index = len(self.signature_doc["urls"])
                    except KeyboardInterrupt:
                        raise
                    except SystemExit:
                        raise
                    except:
                        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

                        errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                        self.logMessage("doWork: error in runTest. %s signature: %s, url: %s, exception: %s" %
                                        (exceptionValue, self.signature_doc["_id"], url, errorMessage))
                url_index += 1

            elif (url_index >= len(self.signature_doc["urls"])):

                if not self.isBetterWorkerAvailable(self.signature_doc):
                    self.debugMessage('doWork: no better worker available, deleting signature %s' % self.signature_doc['_id'])
                    self.testdb.deleteDocument(self.signature_doc, True)
                else:
                    self.debugMessage('doWork: better worker available, setting signature %s worker to None' % self.signature_doc['_id'])
                    self.signature_doc["worker"] = None
                    self.signature_doc["processed_by"][self.document["_id"]] = 1
                    self.testdb.updateDocument(self.signature_doc, True)
                    # Increment the skip value for this view so that we don't retrieve this signature when
                    # we next query the pending jobs.
                    self.viewdata['skip'] += 1

                self.signature_doc            = None
                self.document["signature_id"] = None
                self.document["state"]        = 'completed signature'
                self.document["datetime"]     = sisyphus.utils.getTimestamp()
                self.updateWorker(self.document)
            else:
                self.debugMessage('doWork: ?')


def getBuildData(crashtestdb, worker=None):
    for attempt in crashtestdb.max_db_attempts:
        try:
            supported_versions_rows = crashtestdb.db.views.default.supported_versions()
            break
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

            if not re.search('/(couchquery|httplib2)/', errorMessage):
                raise

            # reconnect to the database in case it has dropped
            crashtestdb.connectToDatabase(None)
            crashtestdb.logMessage('getBuildData: attempt: %d, exception: %s' % (attempt, errorMessage))
            if worker:
                worker.amIOk()

        if attempt == crashtestdb.max_db_attempts[-1]:
            raise Exception("getBuildData: aborting after %d attempts" % (crashtestdb.max_db_attempts[-1] + 1))
        time.sleep(60)

    if len(supported_versions_rows) > 1:
        raise Exception("getBuildData: crashtest database has more than one supported_versions document")

    if len(supported_versions_rows) == 0:
        raise Exception("getBuildData: crashtest database must have one supported_versions document")

    build_data = supported_versions_rows[0]["supported_versions"]

    if attempt > 0:
        crashtestdb.logMessage('getBuildData: attempt: %d, success' % (attempt))

    return build_data

def main():

    global options, this_worker

    this_worker = None

    usage = '''usage: %prog [options]

Example:
%prog -d http://couchserver/crashtest
'''
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--database', action='store', type='string',
                      dest='databaseuri',
                      default='http://127.0.0.1:5984/crashtest',
                      help='uri to crashtest couchdb database')
    parser.add_option('-c', '--comment', action='store', type='string',
                      dest='worker_comment',
                      default='',
                      help='optional text to describe worker configuration')
    parser.add_option('--nodebug', action='store_false', 
                      dest='debug',
                      default=False,
                      help='default - no debug messages')
    parser.add_option('--debug', action='store_true', 
                      dest='debug',
                      help='turn on debug messages')
    (options, args) = parser.parse_args()

    crashtestdb = sisyphus.couchdb.Database(options.databaseuri)

    urimatch = re.search('(https?:)(.*)', options.databaseuri)
    if not urimatch:
        raise Exception('Bad database uri')

    hosturipath    = re.sub(urimatch.group(1), '', options.databaseuri)
    hosturiparts   = urllib.splithost(hosturipath)

    historydburi = urimatch.group(1) + '//' + hosturiparts[0] + '/history'

    crashtestdb = sisyphus.couchdb.Database(options.databaseuri)
    historydb   = sisyphus.couchdb.Database(historydburi)

    exception_counter = 0

    build_data = getBuildData(crashtestdb)

    branches   = [build_data[major_version]['branch'] for major_version in build_data]

    this_worker     = CrashTestWorker(startdir, programPath, crashtestdb, historydb, options.worker_comment, branches, options.debug)

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

            this_worker.signature_doc = None

            exception_counter += 1
            if exception_counter > 100:
                print "Too many errors. Terminating."
                exit(2)

            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

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

    if this_worker is None:
        exit(2)

    if restart:
        this_worker.logMessage('Program restarting', False)
        this_worker.reloadProgram()
    else:
        this_worker.logMessage('Program terminating', False)
        this_worker.testdb.deleteDocument(this_worker.document, False)


