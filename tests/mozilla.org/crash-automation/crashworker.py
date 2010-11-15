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

    def __init__(self, startdir, programPath, couchserveruri, couchdbname, worker_comment, debug):
        sisyphus.worker.Worker.__init__(self, "crashtest", startdir, programPath, couchserveruri, couchdbname, worker_comment, debug)
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
                    'endkey'   : list(key),
                    # when a job is returned, the current_startkey and current_startkey_docid
                    # are set to the values determined by the job and skip is set to 1 so that
                    # the next query will return the next job. This will prevent the server from
                    # continually reading and skipping over the initial pending jobs. The
                    # current values will be reset whenever the skip value is reset to 0.
                    'current_startkey' : None,
                    'current_startkey_docid' : '',
                    # pendingcount tracks the number of job rows retrieved from the most recent request.
                    # processedcount tracks the number of jobs which have already been processed by
                    # this or an equivalent worker. When all jobs for all views for all priorities
                    # for this class of worker have been processed, the worker will go idle for an
                    # extended period so that it does not continually pull job queues which it has
                    # already processed.
                    'pendingcount' : 0,
                    'processedcount' : 0,
                    }
                viewdata['endkey'].append({});
                self.jobviewdata[priority].append(viewdata)
                del key[len(key)-1]

        # self.workers is a dictionary that contains a cache of worker documents
        # keyed on the worker's id.
        # It is used in checkSignatureForWorker to determine if a signature has
        # already been processed by an equivalent worker.

        self.workers = {self.document['_id']: self.document}

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
            self.reloadProgram()

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
                        # do not check signature references here since
                        # this requires the signature document to be
                        # updated prior to the worker update. Rely on
                        # freeOrphanJobs to check worker <-> signature_doc
                        # referential integrity.
                        pass
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

        self.debugMessage('killZombies(crashworker.py)')

        now          = datetime.datetime.now()
        deadinterval = datetime.timedelta(hours=self.zombie_time)
        worker_rows  = self.getAllWorkers()
        this_worker_id = self.document['_id']

        for worker_row in worker_rows:
            worker_row_id = worker_row['_id']

            self.debugMessage('killZombies: checking %s' % worker_row_id)

            if worker_row_id == self.document['_id']:
                # don't zombify ourselves
                continue

            if worker_row['state'] == 'disabled' or worker_row['state'] == 'zombie':
                # don't zombify disabled or zombified workers
                self.debugMessage('killZombies: %s already %s' % (worker_row_id, worker_row['state']))
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

        # kill any test processes still running.
        self.killTest()

        url = sisyphus.utils.encodeUrl(url)

        timestamp = sisyphus.utils.getTimestamp()

        result_doc = {
            "_id"               : "%s_result_%05d_%s" % (self.signature_doc["_id"], url_index, self.document['_id']),
            "type"              : "result_header_crashtest",
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
            "reproduced"        : False,
            "test"              : "crashtest",
            "extra_test_args"   : None,
            "steps"             : [] # steps Spider took on the page.
            }

        self.testdb.createDocument(result_doc)

        page               = "startup"
        executablepath     = ""
        profilename        = ""
        reExecutablePath   = re.compile(r'^environment: TEST_EXECUTABLEPATH=(.*)')
        reProfileName      = re.compile(r'^environment: TEST_PROFILENAME=(.*)')
        reAssertionFail    = re.compile(r'^Assertion fail.*')
        reASSERTION        = re.compile(r'^.?###\!\!\! ASSERTION: (.*), file (.*), line [0-9]+.*')
        reValgrindLeader   = re.compile(r'^==[0-9]+==')
        reSpiderBegin      = re.compile(r'^Spider: Begin loading (.*)')
        reSpider           = re.compile(r'^Spider:')
        reUrlExitStatus    = re.compile(r'^(http.*): EXIT STATUS: (.*) [(].*[)].*')
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
                result_doc['steps'].append(line.strip())

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
                continue

            if self.document["os_name"] == "Windows NT":
                match = reExploitableClass.match(line)
                if match:
                    result_doc["exploitableclass"] = match.group(1)
                    continue
                match = reExploitableTitle.match(line)
                if match:
                    result_doc["exploitabletitle"] = match.group(1)
                    continue

            match = reAssertionFail.match(line)
            if match:
                result_doc["assertionfail"] = match.group(0)
                continue

            match = reASSERTION.match(line)
            if match:
                # record the assertion for later output when we know the test
                assertion_list.append({
                        "message" : match.group(1),
                        "file"    : re.sub('^([a-zA-Z]:/|/[a-zA-Z]/)', '/', re.sub(r'\\', '/', match.group(2))),
                        "datetime" : timestamp,
                        })
                continue

            match = reValgrindLeader.match(line)
            if match:
                valgrind_text += line
                continue

            match = reUrlExitStatus.match(line)
            if match:
                result_doc["exitstatus"]       = match.group(2)
                if re.search('(CRASHED|ABNORMAL)', result_doc["exitstatus"]):
                    result_doc["reproduced"] = True
                else:
                    result_doc["reproduced"] = False

        logfile.close()

        result_doc = self.testdb.saveFileAttachment(result_doc, 'log', logfilename, 'text/plain', True, True)

        if os.path.exists(logfilename):
            os.unlink(logfilename)

        symbolsPath = os.path.join(executablepath, 'crashreporter-symbols')

        self.debugMessage("stackwalkPath: %s, symbolsPath: %s, exists: %s" % (stackwalkPath, symbolsPath, os.path.exists(symbolsPath)))

        if stackwalkPath and os.path.exists(stackwalkPath) and os.path.exists(symbolsPath):
            dumpFiles = glob.glob(os.path.join('/tmp', profilename, 'minidumps', '*.dmp'))
            self.debugMessage("dumpFiles: %s" % (dumpFiles))
            if len(dumpFiles) > 0:
                self.logMessage("runTest: %s: %d dumpfiles found in /tmp/%s" % (url, len(dumpFiles), profilename))

            icrashreport = 0

            for dumpFile in dumpFiles:
                icrashreport += 1
                self.logMessage("runTest: processing dump: %s" % (dumpFile))
                # collect information from the dump's extra file first
                # since it contains information about hangs, plugins, etc.
                data = ''
                extraFile = dumpFile.replace('.dmp', '.extra')
                try:
                    extraFileHandle = open(extraFile, 'r')
                    extradict = {}
                    for extraline in extraFileHandle:
                        data += extraline
                        extrasplit = extraline.rstrip().split('=', 1)
                        extradict[extrasplit[0]] = extrasplit[1]
                except:
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                    self.logMessage('runTest: exception processing extra: %s, %s' % (exceptionValue, errorMessage))

                finally:
                    try:
                        extraFileHandle.close()
                    except:
                        pass

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

                    # if the extra data fingers the plugin file but it doesn't
                    # specify the plugin version, grep it from the crash report
                    if ('PluginFilename' in extradict and
                        'PluginVersion' in extradict and
                        extradict['PluginFilename'] and
                        not extradict['PluginVersion']):
                        rePluginVersion = re.compile(r'0x[0-9a-z]+ \- 0x[0-9a-z]+  %s  (.*)' % extradict['PluginFilename'])

                        match = re.search(rePluginVersion, stdout)
                        if match:
                            extradict['PluginVersion'] =  match.group(1)

                except:
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                    self.logMessage('runTest: exception processing dump: %s, %s' % (exceptionValue, errorMessage))

                result_doc["reproduced"] = True

                self.process_crashreport(result_doc["_id"], product, branch, buildtype, timestamp, stdout, page, "crashtest", extra_test_args, extradict)

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
                branches_doc  = self.testdb.getDocument('branches')

                for worker_doc in worker_rows:
                    # Skip other workers who match us exactly but do reissue a
                    # signature for us so that we can test if the crash is also
                    # reproducible on the same machine where it originally occured.
                    if (worker_doc['_id']        != self.document['_id'] and
                        worker_doc['os_name']    == self.document['os_name'] and
                        worker_doc['cpu_name']   == self.document['cpu_name'] and
                        worker_doc['os_version'] == self.document['os_version']):
                        continue

                    for major_version in branches_doc["major_versions"]:

                        # PowerPC is not supported after Firefox 3.6
                        if major_version > '0306' and worker_doc['cpu_name'] == 'ppc':
                            continue

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
                self.logMessage('runTest: unable to duplicate signature %s for reproduction: %s' % (self.signature_doc, errorMessage))

        # process any remaining assertion or valgrind messages.
        self.process_assertions(result_doc["_id"], product, branch, buildtype, timestamp, assertion_list, page, "crashtest", extra_test_args)
        valgrind_list = self.parse_valgrind(valgrind_text)
        self.process_valgrind(result_doc["_id"], product, branch, buildtype, timestamp, valgrind_list, page, "crashtest", extra_test_args)

    def getMatchingWorkerIds(self, startkey=None, endkey=None):

        matching_worker_rows = self.getRows(self.testdb.db.views.crashtest.matching_workers, startkey=startkey, endkey=endkey)
        return matching_worker_rows

    def checkIfUrlAlreadyTested(self, signature_doc, url_index):

        startkey = ["result_header_crashtest", "%s_result_%05d_%s" % (signature_doc["_id"], url_index, self.document['_id'])]
        endkey   = ["result_header_crashtest", "%s_result_%05d_%s" % (signature_doc["_id"], url_index, self.document['_id']), {}];
        result_rows = self.getRows(self.testdb.db.views.bughunter.results_by_type, startkey=startkey, endkey=endkey, include_docs=True)
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

    def getPendingJobs(self, startkey=None, startkey_docid=None, endkey=None, skip=None, limit=1000000):

        if skip is None:
            skip = 0

        for attempt in self.testdb.max_db_attempts:
            try:
                pending_job_rows = self.testdb.db.views.crashtest.pending_jobs(startkey=startkey,
                                                                               startkey_docid=startkey_docid,
                                                                               endkey=endkey,
                                                                               skip=skip,
                                                                               limit=limit)
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

        self.debugMessage('getPendingJobs: startkey: %s, startkey_docid: %s, endkey: %s, matches: %d' % (startkey, startkey_docid, endkey, len(pending_job_rows)))

        return pending_job_rows

    def getAllJobs(self):

        job_rows = self.getRows(self.testdb.db.views.crashtest.jobs_by_worker)

        return job_rows

    def isBetterWorkerAvailable(self, signature_doc):

        self.debugMessage('isBetterWorkerAvailable: checking signature %s' % signature_doc['_id'])

        # try for an exact  match on the signature's os_name, os_version, cpu_name
        # exact matches are by definition the best.
        startkey = [signature_doc["os_name"], signature_doc["os_version"], signature_doc["cpu_name"]]
        endkey   = [signature_doc["os_name"], signature_doc["os_version"], signature_doc["cpu_name"], {}]

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
        endkey   = [signature_doc["os_name"], signature_doc["os_version"], {}]

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
        endkey   = [signature_doc["os_name"], {}]

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
                    # checkSignatureForWorker suffers from a race condition when updating
                    # the signature and worker to contain each others ids. If freeOrphan jobs
                    # runs during the period between the update of the signature and the update
                    # of the worker, it will erroneously flag the job as orphaned and will
                    # cause a document update conflict when it removes the worker id from the
                    # signature. We limit the possibility of losing the race by limiting the
                    # time resolution of the orphan check.
                    now = datetime.datetime.now()
                    worker_timestamp = sisyphus.utils.convertTimestamp(worker_doc['datetime'])
                    if now - worker_timestamp < datetime.timedelta(seconds=60):
                        self.debugMessage("freeOrphanJobs: ignoring race condition: job %s's worker %s is working on %s." %
                                          (signature_id,  worker_id, worker_doc["signature_id"]))
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

            signature_id  = pending_job["signature_id"]
            self.debugMessage("checkSignatureForWorker: checking signature %s" % signature_id)
            signature_doc = self.testdb.getDocument(signature_id)

            if signature_doc:
                # keep track of the current signature so we won't try it again.
                self.viewdata['current_startkey'] = [signature_doc['priority'],
                                                     signature_doc['os_name'],
                                                     signature_doc['cpu_name'],
                                                     signature_doc['os_version'],
                                                     -len(signature_doc['urls'])]
                self.viewdata['current_startkey_docid'] = signature_doc['_id']
                self.viewdata['skip'] = 1

            if not signature_doc or signature_doc["worker"]:
                self.debugMessage("checkSignatureForWorker: race condition: someone else got the signature document %s" % signature_id)
                continue

            # Check if the signature has already been processed by ourselves or another worker
            # with the same operating system, operating system version and cpu type.
            processed_by_equivalent_worker = False
            for other_worker_id in signature_doc["processed_by"]:

                if other_worker_id in self.workers:
                    other_worker = self.workers[other_worker_id]
                else:
                    other_worker = self.testdb.getDocument(other_worker_id)
                    if other_worker:
                        self.workers[other_worker['_id']] = other_worker

                if (other_worker and
                    self.document['os_name']    == other_worker['os_name'] and
                    self.document['os_version'] == other_worker['os_version'] and
                    self.document['cpu_name']   == other_worker['cpu_name']):
                    processed_by_equivalent_worker = True
                    self.debugMessage("checkSignatureForWorker: %s already processed signature %s" % (other_worker_id, signature_id))
                    break

            if processed_by_equivalent_worker:

                # Depending on the population of workers, the worker
                # was not the best at the time it was originally
                # processed the signature, but if we are the best now,
                # we can go ahead and delete it and try for the next
                # job

                self.viewdata['processedcount'] += 1

                if not self.isBetterWorkerAvailable(signature_doc):
                    self.debugMessage("checkSignatureForWorker: there is not a better worker available, deleting signature %s" % signature_id)
                    try:
                        self.testdb.deleteDocument(signature_doc)
                    except KeyboardInterrupt:
                        raise
                    except SystemExit:
                        raise
                    except:
                        # ignore conflicts.
                        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

                        errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                        self.logMessage("checkSignatureForWorker: %s, signature: %s, exception: %s" %
                                        (exceptionValue, signature_doc["_id"], errorMessage))
                continue

            if signature_doc['major_version'] > '0306' and self.document['cpu_name'] == 'ppc':
                # PowerPC is not supported after Firefox 3.6
                # processed the signature. If we are the best worker for this signature,
                # we can go ahead and delete it and try for the next
                # job

                self.viewdata['processedcount'] += 1

                if not self.isBetterWorkerAvailable(signature_doc):
                    self.debugMessage("checkSignatureForWorker: there is not a better worker available, deleting signature %s" % signature_id)
                    try:
                        self.testdb.deleteDocument(signature_doc)
                    except KeyboardInterrupt:
                        raise
                    except SystemExit:
                        raise
                    except:
                        # ignore conflicts.
                        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

                        errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                        self.logMessage("checkSignatureForWorker: %s, signature: %s, exception: %s" %
                                        (exceptionValue, signature_doc["_id"], errorMessage))
                continue

            # update the signature and this worker
            # signature_doc["worker"] <-> self.document["_id"].

            try:
                try:
                    # update worker first to get datetime timestamp for use
                    # in checking race conditions with freeOrphanJobs
                    self.debugMessage("checkSignatureForWorker: update worker %s's signature" % self.document["_id"])
                    self.document["signature_id"] = signature_id
                    self.updateWorker(self.document)
                except KeyboardInterrupt:
                    raise
                except SystemExit:
                    raise
                except:
                    # exception updating worker
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                    self.logMessage("checkSignatureForWorker: exception %s updating worker: %s" %
                                    (exceptionValue, errorMessage))

                self.debugMessage("checkSignatureForWorker: update signature %s's worker" % signature_id)
                signature_doc["worker"] = self.document["_id"]
                self.testdb.updateDocument(signature_doc)

            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                # exception updating signature_doc
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                self.logMessage("checkSignatureForWorker: exception %s updating signature: %s, %s" %
                                (exceptionValue, signature_doc["_id"], errorMessage))
                signature_doc = None

                # update worker to remove signature
                try:
                    self.document["signature_id"] = None
                    self.updateWorker(self.document)
                except:
                    # exception updating worker
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                    self.logMessage("checkSignatureForWorker: exception %s updating worker: %s, %s" %
                                    (exceptionValue, self.document["_id"], errorMessage))

            if signature_doc:
                self.debugMessage("checkSignatureForWorker: returning signature %s" % signature_doc["_id"])
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

        limit         = 64 # 64 * 32 byte id = 2048 bytes.
        signature_doc = None

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
                    viewdata['current_startkey'] = None
                    viewdata['current_startkey_docid'] = ''
                    viewdata['skip'] = 0
                    viewdata['pendingcount'] = 0
                    viewdata['processedcount'] = 0

        for prioritydata in self.jobviewdata:
            # process views for this priority

            self.debugMessage("getSignatureForWorker: prioritydata: %s" % (prioritydata))

            if signature_doc:
                break

            for self.viewdata in prioritydata:

                if self.viewdata['skip'] < 0:
                    continue

                while True:
                    # keep looping until we get a job or run out.

                    self.debugMessage("getSignatureForWorker: self.viewdata['startkey]': %s, self.viewdata['endkey']: %s, self.viewdata['skip']: %d, self.viewdata['current_startkey']: %s, self.viewdata['current_startkey_docid']: %s" % (self.viewdata['startkey'], self.viewdata['endkey'], self.viewdata['skip'], self.viewdata['current_startkey'], self.viewdata['current_startkey_docid']))

                    if self.viewdata['current_startkey']:
                        startkey = self.viewdata['current_startkey']
                        startkey_docid = self.viewdata['current_startkey_docid']
                    else:
                        startkey = self.viewdata['startkey']
                        startkey_docid = ''

                    self.debugMessage("getSignatureForWorker: startkey: %s, startkey_docid: %s" % (startkey, startkey_docid))

                    skip = self.viewdata['skip']
                    endkey = self.viewdata['endkey']

                    job_rows = self.getPendingJobs(startkey = startkey,
                                                   startkey_docid = startkey_docid,
                                                   endkey   = endkey,
                                                   skip     = skip,
                                                   limit    = limit)

                    if len(job_rows) == 0:
                        self.viewdata['current_startkey'] = None
                        self.viewdata['current_startkey_docid'] = ''
                        self.viewdata['skip'] = -1
                        self.viewdata['pendingcount'] = 0
                        self.viewdata['processedcount'] = 0
                        self.debugMessage("getSignatureForWorker: no jobs for startkey: %s, endkey: %s, skip: %d, current_startkey: %s, current_startkey_docid: %s" % (self.viewdata['startkey'], self.viewdata['endkey'], self.viewdata['skip'], self.viewdata['current_startkey'], self.viewdata['current_startkey_docid']))
                        break # while True

                    self.viewdata['pendingcount'] = len(job_rows)

                    signature_doc = self.checkSignatureForWorker(job_rows)
                    if signature_doc:
                        break # while True

                if signature_doc:
                    break # for self.viewdata

            if signature_doc:
                break # for prioritydata

        if not signature_doc:
            # if there are no more jobs or if all remaining jobs have already been processed
            # by this worker's class of worker, then go idle for an hour.
            more_jobs_available = False
            for prioritydata in self.jobviewdata:
                for viewdata in prioritydata:
                    if viewdata['skip'] != -1 and viewdata['pendingcount'] != viewdata['processedcount']:
                        more_jobs_available = True
                        break
            if not more_jobs_available:
                self.logMessage("getSignatureForWorker: no more jobs, going idle.")
                time.sleep(3600)

        self.debugMessage("getSignatureForWorker: returning signature %s" % signature_doc)
        return signature_doc

    def doWork(self):

        product   = "firefox"
        buildtype = "debug"
        waittime  = 0

        build_checkup_interval = datetime.timedelta(hours=3)
        checkup_interval = datetime.timedelta(minutes=5)
        last_checkup_time = datetime.datetime.now() - 2*checkup_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate()
                self.testdb.checkDatabase()
                self.killZombies()
                self.freeOrphanJobs()
                last_checkup_time = datetime.datetime.now()

            sys.stdout.flush()
            time.sleep(waittime)
            waittime = 0

            if self.signature_doc:
                build_doc    = self.BuildDocument(product, branch, buildtype,
                                                  self.document["os_name"], self.document["cpu_name"])
                build_needed = self.NewBuildNeeded(build_doc, build_checkup_interval)
            else:
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
                    branches_doc  = self.testdb.getDocument("branches")
                    branch        = branches_doc["version_to_branch"][major_version]

                    build_doc    = self.BuildDocument(product, branch, buildtype,
                                                      self.document["os_name"], self.document["cpu_name"])
                    build_needed = self.NewBuildNeeded(build_doc, build_checkup_interval)

                else:
                    url_index     = -1
                    major_version = None
                    branch_data   = None
                    branch        = None
                    waittime      = 1

                    if self.document["state"] != "idle":
                        self.debugMessage('No signatures available to process, going idle.')

                    # XXX: right now we may need to update here to keep the worker alive
                    # but when we have a worker heartbeat thread we can move these
                    # updates to under the conditional above.
                    self.document["state"]    = "idle"
                    self.document["datetime"] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    continue

            if (options.build and
                (build_needed or not self.document[branch]["builddate"] or
                 not self.document[branch]["buildsuccess"] or
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
                    # release the signature.
                    # Note that this signature will be temporarily skipped until the worker's
                    # viewdata startkey/startkey_docid values are reset. This will allow the
                    # worker to continue to process signatures for other branches rather than
                    # blocking on a signature for a branch which can not be built.
                    self.document["signature_id"] = None
                    self.document["state"]        = 'build failure'
                    self.document["datetime"]     = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    self.signature_doc["worker"]  = None
                    self.testdb.updateDocument(self.signature_doc, True)
                    self.signature_doc = None

            elif (not options.build and build_doc["buildavailable"] and
                  (not self.document[branch]["buildsuccess"] or
                   build_doc["builddate"] > self.document[branch]["builddate"])):

                # We are not a builder, and a build is available to
                # download and either we do not have a build or the
                # available build is newer. Download and install the
                # newer build.

                if not self.DownloadAndInstallBuild(build_doc):
                    # We failed to install the new build.
                    # Release the signature. We have already recorded the skip value for this view
                    # so that we don't retrieve this signature when we next query the pending jobs.
                    self.logMessage('doWork: failed downloading new %s %s %s build' %
                                    (product, branch, buildtype))
                    self.document["state"]        = 'download failure'
                    self.document["datetime"]     = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    self.signature_doc["worker"] = None
                    self.testdb.updateDocument(self.signature_doc, True)
                    self.signature_doc = None

            elif (self.document[branch]["buildsuccess"] and url_index < len(self.signature_doc["urls"])):

                # Either the build in the builds database and our local build are both current
                # or both are stale. Continue to test with a stale build until a fresh one becomes
                # available.
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
                        self.runTest(product, branch, buildtype, url, url_index, extra_test_args)
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

            elif (self.document[branch]["buildsuccess"] and url_index >= len(self.signature_doc["urls"])):

                # the update worker code is duplicated in order that the worker update occur immediately
                # prior to the signature update in order to reduce the chance of race conditions when
                # checking referential integrity.
                if not self.isBetterWorkerAvailable(self.signature_doc):
                    self.debugMessage('doWork: no better worker available, deleting signature %s' % self.signature_doc['_id'])
                    self.document["signature_id"] = None
                    self.document["state"]        = 'completed signature'
                    self.document["datetime"]     = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    self.testdb.deleteDocument(self.signature_doc, True)
                else:
                    self.debugMessage('doWork: better worker available, setting signature %s worker to None' % self.signature_doc['_id'])
                    self.document["signature_id"] = None
                    self.document["state"]        = 'completed signature'
                    self.document["datetime"]     = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    self.signature_doc["worker"] = None
                    self.signature_doc["processed_by"][self.document["_id"]] = 1
                    self.testdb.updateDocument(self.signature_doc, True)

                self.signature_doc            = None
            else:
                self.logMessage('doWork: no %s %s %s builds are available' % (product, branch, buildtype))
                time.sleep(300)

def main():

    global options, this_worker

    this_worker = None

    usage = '''usage: %prog [options]

Example:
%prog --couch http://couchserver

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

    parser.add_option('--nodebug', action='store_false',
                      dest='debug',
                      default=False,
                      help='default - no debug messages')

    parser.add_option('--debug', action='store_true',
                      dest='debug',
                      help='turn on debug messages')

    (options, args) = parser.parse_args()

    if options.couchserveruri is None:
         parser.print_help()
         exit(1)

    exception_counter = 0

    this_worker     = CrashTestWorker(startdir, programPath, options.couchserveruri, options.databasename, options.worker_comment, options.debug)

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


