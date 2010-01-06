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
import traceback
import time
import sys
import subprocess
import tempfile
import re
import datetime
import platform
import couchquery
import base64 # for encoding document attachments.
import urlparse
import urllib
import glob
import random
#import threading
import signal

# http://code.google.com/p/httplib2/
import httplib2

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json


debug = True

programPath = os.path.abspath(os.path.realpath(os.path.dirname(sys.argv[0]))) + '/' + os.path.basename(sys.argv[0])
print programPath
programModTime = os.stat(programPath)[stat.ST_MTIME]

db               = None
dburi            = None
database_status  = None
max_db_attempts  = range(10)
this_worker_doc  = None
zombie_time      = 6      # if a worker hasn't updated datetime in zombie_time hours, it will be killed.
sisyphus_dir     = os.environ["TEST_DIR"]

os.chdir(sisyphus_dir)
os.environ["TEST_TOPSITE_TIMEOUT"]="300"
os.environ["TEST_TOPSITE_PAGE_TIMEOUT"]="120"
os.environ["XPCOM_DEBUG_BREAK"]="warn"

stackwalkPath = os.environ.get('MINIDUMP_STACKWALK', "/usr/local/bin/minidump_stackwalk")

def makeUnicodeString(s):
    # http://farmdev.com/talks/unicode/
    if isinstance(s, basestring):
        if not isinstance(s, unicode):
            s = unicode(s, "utf-8", errors='replace')
    return s

def formatException(etype, evalue, etraceback):
    return str(traceback.format_exception(etype, evalue, etraceback))

def checkForUpdate():
    # Note this will restart the program leaving the this_worker_doc
    # in the database where it will be picked up on restart
    # preserving the most recent build data.
    if os.stat(programPath)[stat.ST_MTIME] != programModTime:
        message = 'checkForUpdate: Program change detected. Reloading from disk.'
        logMessage(message)
        if this_worker_doc is not None:
            try:
                this_worker_doc['state'] = message
                if this_worker_doc["signature_id"]:
                    signature_doc = getDocument(this_worker_doc["signature_id"])
                    if signature_doc:
                        if this_worker_doc["_id"] == signature_doc["worker"]:
                            signature_doc["worker"] = None
                            updateDocument(signature_doc)
                        else:
                            debugMessage("checkForUpdate: worker's linked signature %s belongs to %s" % (this_worker_doc["signature_id"], signature_doc["worker"]))
                    else:
                        debugMessage("checkForUpdate: worker's linked signature %s is deleted" % this_worker_doc["signature_id"])

                updateWorker(this_worker_doc)
            except:
                pass
        sys.stdout.flush()
        sys.argv[0] = programPath
        sys.argv.insert(0, programPath)
        os.execvp("python", sys.argv)

def getTimestamp(hiresolution=False):
    timestamp = datetime.datetime.now()
    datetimestamp = datetime.datetime.strftime(timestamp, "%Y-%m-%dT%H:%M:%S")
    if hiresolution:
        datetimestamp = "%s.%06d" % (datetimestamp, timestamp.microsecond)
    return datetimestamp

def convertTimestamp(s):
    try:
        s = re.sub('\.[0-9]*$', '', s)
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except KeyboardInterrupt:
        raise
    except:
        pass

    return datetime.datetime.strptime('2009-01-1T00:00:00', "%Y-%m-%dT%H:%M:%S")

def logMessage(s):
    id = None
    if not this_worker_doc:
        id = os.uname()[1]
    else:
        id = this_worker_doc["_id"]

    s = makeUnicodeString(s)
    log_doc = {
        "datetime"  : getTimestamp(hiresolution=True),
        "worker_id" : id,
        "message"   : u"%s: %s" % (id, s),
        "type"      : "log"
        }

    print "%s: %s: %s" % (id, log_doc["datetime"], log_doc["message"])

    # don't use createDocument here as it may cause an infinite loop
    # since logMessage is called from inside the exception handler of
    # createDocument
    for attempt in max_db_attempts:
        try:
            docinfo = db.create(log_doc)
            log_doc["_id"]  = docinfo["id"]
            log_doc["_rev"] = docinfo["rev"]
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)
            print('logMessage: attempt: %d, exception: %s' % (attempt, errorMessage))

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()

        if attempt == max_db_attempts[-1]:
            raise Exception("logMessage: aborting after %d attempts" % (max_db_attempts[-1]+1))
        time.sleep(60)

def debugMessage(s):
    if debug:
        logMessage(s)

def buildProduct(product, branch, buildtype):
    buildsteps  = "checkout build"
    buildchangeset = None
    buildsuccess = True

    logMessage('begin building %s %s %s' % (product, branch, buildtype))

    proc = subprocess.Popen(
        [
            sisyphus_dir + "/bin/builder.sh",
            "-p", product,
            "-b", branch,
            "-T", buildtype,
            "-B", buildsteps
            ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    stdout, stderr = proc.communicate()

    if re.search('^FATAL ERROR', stderr, re.MULTILINE):
        buildsuccess = False

    logs = stdout.split('\n')
    for logline in logs:
        logfilenamematch = re.search('log: (.*\.log)', logline)
        if logfilenamematch:
            logfilename = logfilenamematch.group(1)
            checkoutlogmatch = re.search('.*checkout.log', logfilename)
            if checkoutlogmatch:
                logfile = open(logfilename, 'rb')
                for line in logfile:
                    matchchangeset = re.search('build changeset:.* id (.*)', line)
                    if matchchangeset:
                        buildchangeset = matchchangeset.group(1)
                logfile.close()

            # only delete the log file if successful.
            if buildsuccess:
                os.unlink(logfilename)

    if buildsuccess:
        logMessage('success building %s %s %s changeset %s' % (product, branch, buildtype, buildchangeset))
    else:
        logMessage('failure building %s %s %s changeset %s' % (product, branch, buildtype, buildchangeset))

    return {"changeset" : buildchangeset, "success" : buildsuccess}

def clobberProduct(product, branch, buildtype):
    buildsteps  = "clobber"
    buildchangeset = None
    buildsuccess = True

    logMessage('begin clobbering %s %s %s' % (product, branch, buildtype))

    proc = subprocess.Popen(
        [
            sisyphus_dir + "/bin/builder.sh",
            "-p", product,
            "-b", branch,
            "-T", buildtype,
            "-B", buildsteps
            ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    stdout, stderr = proc.communicate()

    if re.search('^FATAL ERROR', stderr, re.MULTILINE):
        buildsuccess = False

    logs = stdout.split('\n')
    for logline in logs:
        logfilenamematch = re.search('log: (.*\.log)', logline)
        if logfilenamematch:
            logfilename = logfilenamematch.group(1)
            # only delete the log file if successful.
            if buildsuccess:
                os.unlink(logfilename)

    if buildsuccess:
        logMessage('success clobbering %s %s %s' % (product, branch, buildtype))
    else:
        logMessage('failure clobbering %s %s %s' % (product, branch, buildtype))

    return buildsuccess

def testUrl(product, branch, buildtype, url):
    global this_worker_doc

    # encode the url
    url            = makeUnicodeString(url)
    urlParseObject = urlparse.urlparse(url)
    urlPieces      = [urllib.quote(urlpiece) for urlpiece in urlParseObject]
    url            = urlparse.urlunparse(urlPieces)

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

    page             = ""
    executablepath   = ""
    profilename      = ""

    reExecutablePath   = re.compile(r'environment: TEST_EXECUTABLEPATH=(.*)')
    reProfileName      = re.compile(r'environment: TEST_PROFILENAME=(.*)')
    reSpiderBegin      = re.compile(r'Spider: Begin loading (.*)')
    reExploitableClass = re.compile(r'^Exploitability Classification: (.*)')
    reExploitableTitle = re.compile(r'^Recommended Bug Title: (.*)')
    reAssertionFail    = re.compile(r'Assertion fail.*')
    reUrlExitStatus    = re.compile(r'(http.*): EXIT STATUS: (.*) [(].*[)].*')
    reASSERTION        = re.compile(r'.*ASSERTION: (.*), file (.*)')

    result = {
        "type": "result",
        "url": url,
        "ASSERTIONS" : {},
        "reproduced" : False,
        "_attachments" : {
            "log" : {
                "content_type" : "text/plain",
                "data"         : u""
                },
            "crashreport" : {
                "content_type" : "text/plain",
                "data"         : u""
                },
            "extra" : {
                "content_type" : "text/plain",
                "data"         : u""
                },
            }
        }

    logfile = open(logfilename, "r")
    data    = u""

    while 1:
        line = logfile.readline()
        if not line:
            break

        # decode to unicode
        line = makeUnicodeString(line)

        if not executablepath:
            match = reExecutablePath.match(line)
            if match:
                executablepath = match.group(1)

        if not profilename:
            match = reProfileName.match(line)
            if match:
                profilename = match.group(1)

        if not page:
            match = reSpiderBegin.match(line)
            if match:
                page = match.group(1)

        # only collect the log after Spider begins loading
        if page:
            data += line

        if this_worker_doc["os_name"] == "Windows NT":
            match = reExploitableClass.match(line)
            if match:
                result["exploitableclass"] = match.group(1)
            match = reExploitableTitle.match(line)
            if match:
                result["exploitabletitle"] = match.group(1)

        match = reAssertionFail.match(line)
        if match:
            result["assertionfail"] = match.group(0)

        match = reASSERTION.match(line)
        if match:
            if not match.group(1) in result["ASSERTIONS"]:
                result["ASSERTIONS"][match.group(1)] = 0
            result["ASSERTIONS"][match.group(1)] += 1

        match = reUrlExitStatus.match(line)
        if match:
            result["exitstatus"]       = match.group(2)
            if re.search('(CRASHED|ABNORMAL)', result["exitstatus"]):
                result["reproduced"] = True
            else:
                result["reproduced"] = False

    logfile.close()
    if not result["reproduced"]:
        os.unlink(logfilename)

    result["_attachments"]["log"]["data"] = base64.b64encode(data.encode('utf-8'))

    symbolsPath = executablepath + '/crashreporter-symbols'

    #debugMessage("stackwalkPath: %s, symbolsPath: %s, exists: %s" % (stackwalkPath, symbolsPath, os.path.exists(symbolsPath)))

    if stackwalkPath and os.path.exists(stackwalkPath) and os.path.exists(symbolsPath):
        dumpFiles = glob.glob(os.path.join('/tmp/' + profilename + '/minidumps', '*.dmp'))
        #debugMessage("dumpFiles: %s" % (dumpFiles))
        if len(dumpFiles) > 0:
            logMessage("testUrl: %s: %d dumpfiles found in /tmp/%s" % (url, len(dumpFiles), profilename))

        for dumpFile in dumpFiles:
            logMessage("testUrl: processing dump: %s" % (dumpFile))
            # use timed_run.py to run stackwalker since it can hang on
            # win2k3 at least...
            debugMessage("/usr/bin/python " + sisyphus_dir + "/bin/timed_run.py")
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
            #debugMessage("stackwalking: stdout: %s" % (stdout))
            #debugMessage("stackwalking: stderr: %s" % (stderr))

            data = makeUnicodeString(stdout)

            result["_attachments"]["crashreport"]["data"] += base64.b64encode(data.encode('utf-8'))

            data = ''
            extraFile = dumpFile.replace('.dmp', '.extra')
            extraFileHandle = open(extraFile, 'r')
            for extraline in extraFileHandle:
                data += extraline
            data = makeUnicodeString(data)
            result["_attachments"]["extra"]["data"] += base64.b64encode(data.encode('utf-8'))


    return result

def getBuildData():
    for attempt in max_db_attempts:
        try:
            supported_versions_rows = db.views.signatures.supported_versions()
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getBuildData: attempt: %d, exception: %s' % (attempt, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getBuildData: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if len(supported_versions_rows) > 1:
        raise Exception("getBuildData: crashtest database has more than one supported_versions document")

    if len(supported_versions_rows) == 0:
        raise Exception("getBuildData: crashtest database must have one supported_versions document")

    build_data = supported_versions_rows[0]["supported_versions"]

    if attempt > 0:
        logMessage('getBuildData: attempt: %d, success' % (attempt))

    return build_data

def getPendingDates(key=None):
    for attempt in max_db_attempts:
        try:
            pending_dates_rows = db.views.signatures.pending_dates(group=True)
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getPendingDates: attempt: %d, key: %s, exception: %s' % (attempt, key, errroMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getPendingDates: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('getPendingDates: attempt: %d, success' % (attempt))

    if len(pending_dates_rows) == 0:
        return None

    return pending_dates_rows.keys()

def getWorkers(key=None):
    for attempt in max_db_attempts:
        try:
            worker_rows = db.views.signatures.workers(key=key)
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getWorkers: attempt: %d, key: %s, exception: %s' % (attempt, key, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getWorkers: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('getWorkers: attempt: %d, success' % (attempt))

    return worker_rows

def getMatchingWorkerIds(startkey=None, endkey=None):
    for attempt in max_db_attempts:
        try:
            matching_worker_rows = db.views.signatures.matching_workers(startkey=startkey, endkey=endkey)
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getMatchingWorkerIds: attempt: %d, startkey: %s, endkey: %s, exception: %s' %
                           (attempt, startkey, endkey, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getMatchingWorkerIds: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('getMatchingWorkerIds: attempt: %d, success' % (attempt))

    return matching_worker_rows

def getAllWorkers(key=None):
    for attempt in max_db_attempts:
        try:
            worker_rows = db.views.signatures.workers()
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getAllWorkers: attempt: %d, key: %s, exception: %s' % (attempt, key, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getAllWorkers: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('getAllWorkers: attempt: %d, success' % (attempt))

    return worker_rows

def checkIfUrlAlreadyTested(signature_doc, url_index):
    for attempt in max_db_attempts:
        try:
            startkey = "%s_result_%05d" % (signature_doc["_id"], url_index)
            endkey   = startkey + '\u9999';
            result_rows = db.views.signatures.results_all(startkey=startkey,endkey=endkey)
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('checkIfUrlAlreadyTested: attempt: %d, startkey: %s, endkey: %s, exception: %s' %
                           (attempt, startkey, endkey, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("checkIfUrlAlreadyTested: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('checkIfUrlAlreadyTested: attempt: %d, success' % (attempt))

    #debugMessage('checkIfUrlAlreadyTested: %s' % (len(result_rows) != 0))

    return len(result_rows) != 0

def getPendingJobs(startkey=None, endkey=None, limit=1000000):

    for attempt in max_db_attempts:
        try:
            pending_job_rows = db.views.signatures.pending_jobs(startkey=startkey,endkey=endkey,limit=limit)
            #debugMessage('getPendingJobs: startkey: %s, endkey: %s, matches: %d' % (startkey, endkey, len(pending_job_rows)))
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getPendingJobs: attempt: %d, startkey: %s, endkey: %s, exception: %s' %
                           (attempt, startkey, endkey, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getPendingJobs: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('getPendingJobs: attempt: %d, success' % (attempt))

    #debugMessage('getPendingJobs: startkey=%s, endkey=%s, count: %d' % (startkey, endkey, len(pending_job_rows)))

    return pending_job_rows

def getJobsByWorker(startkey=None, endkey=None):

    for attempt in max_db_attempts:
        try:
            job_rows = db.views.signatures.jobs_by_worker(startkey=startkey,endkey=endkey)
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getJobsByWorker: attempt: %d, startkey: %s, endkey: %s, exception: %s' %
                           (attempt, startkey, endkey, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getJobsByWorker: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('getJobsByWorker: attempt: %d, success' % (attempt))

    #debugMessage('getJobsByWorker: startkey=%s, endkey=%s, count: %d' % (startkey, endkey, len(job_rows)))

    return job_rows

def getAllJobs():

    for attempt in max_db_attempts:
        try:
            job_rows = db.views.signatures.jobs_by_worker()
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getAllJobs: attempt: %d, exception: %s' % (attempt, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getAllJobs: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('getAllJobs: attempt: %d, success' % (attempt))

    #debugMessage('getAllJobs: count: %d' % (len(job_rows)))

    return job_rows

def getDocument(id):
    document = None

    for attempt in max_db_attempts:
        try:
            document = db.get(id)
            break
        except couchquery.CouchDBDocumentDoesNotExist:
            return None
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('getDocument: attempt: %d, id: %s, exception: %s' %
                           (attempt, id, errorMessage))
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("getDocument: aborting after %d attempts" % (max_db_attempts[-1] + 1))

        time.sleep(60)

    if attempt > 0:
        logMessage('getDocument: attempt: %d, success' % (attempt))

    return document

def createDocument(document):

    for attempt in max_db_attempts:
        try:
            docinfo = db.create(document)
            document["_id"] = docinfo["id"]
            document["_rev"] = docinfo["rev"]
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('createDocument: attempt: %d, type: %s, exception: %s' % (attempt, document['type'], errorMessage))
            elif exceptionType == couchquery.CouchDBException and re.search('Document update conflict', str(exceptionValue)):
                temp_document = getDocument(document["_id"])
                document["_rev"] = temp_document["_rev"]
                logMessage('createDocument: attempt: %d, update type: %s, _id: %s, _rev: %s' %
                           (attempt, document['type'], document["_id"], document["_rev"]))
                updateDocument(document, owned=True)
                break
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("createDocument: aborting after %d attempts" % (max_db_attempts[-1]+1))

        time.sleep(60)

    if attempt > 0:
        logMessage('createDocument: attempt: %d, success' % (attempt))

def updateDocument(document, owned=False):
    """
    Update a document handling database connection errors.

    owned = False (the default) means that document update conflicts
    will throw an Exception('updateDocumentConflict') which must be handled
    by the calller.

    owned = True means the current document will overwrite any conflicts
    due to other updates to the document.
    """

    for attempt in max_db_attempts:

        try:
            docinfo = db.update(document)
            document["_rev"] = docinfo["rev"]
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('updateDocument: attempt: %d, type: %s, exception: %s' % (attempt, document['type'], errorMessage))
            elif exceptionType == couchquery.CouchDBException and re.search('Document update conflict', str(exceptionValue)):
                if not owned:
                    raise Exception('updateDocumentConflict')

                logMessage('updateDocument: owner will overwrite changes to type: %s, id: %s, rev: %s, exception: %s' %
                           (document['type'], document['_id'], document['_rev'], errorMessage))
                temp_document = getDocument(document["_id"])
                document["_rev"] = temp_document["_rev"]
                docinfo = db.update(document)
                document["_rev"] = docinfo["rev"]
                break
            else:
                raise
        if attempt == max_db_attempts[-1]:
            raise Exception("updateDocument: aborting after %d attempts" % (max_db_attempts[-1] + 1))
        time.sleep(60)

    if attempt > 0:
        logMessage('updateDocument: attempt: %d, success' % (attempt))

def deleteDocument(document, owned=False):
    """
    Delete a document handling database connection errors.

    owned = False (the default) means that document update conflicts
    will throw an Exception('deleteDocumentConflict') which must be handled
    by the calller.

    owned = True means the current document will delete the document regardless of
    any conflicts due to other updates to the document.
    """

    for attempt in max_db_attempts:
        try:
            docinfo = db.delete(document)
            document["_rev"] = docinfo["rev"]
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt:
                raise

            errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                connectToDatabase()
                logMessage('deleteDocument: attempt: %d, type: %s, id: %s, rev: %s, exception: %s' %
                           (attempt, document['type'], document['_id'], document['_rev'], errorMessage))
            elif exceptionType == couchquery.CouchDBException:
                if re.search('Delete failed {"error":"not_found","reason":"deleted"}', str(exceptionValue)):
                    logMessage('deleteDocument: ignore already deleted document. type: %s, id: %s' % (document["type"], document["_id"]))
                    break
                if not owned:
                    raise Exception('deleteDocumentConflict')
                if re.search('Document update conflict', str(exceptionValue)):
                    logMessage('deleteDocument: owner will attempt to deleted updated document')
                    temp_document = getDocument(document["_id"])
                    document["_rev"] = temp_document["_rev"]
                    docinfo = db.delete(document)
                    document["_rev"] = docinfo["rev"]
                    break
            else:
                raise

        if attempt == max_db_attempts[-1]:
            raise Exception("deleteDocument: aborting after %d attempts" % (max_db_attempts[-1] + 1))

        time.sleep(60)

    if attempt > 0:
        logMessage('deleteDocument: attempt: %d, success' % (attempt))

def isBetterWorkerAvailable(signature_doc):

    #debugMessage('isBetterWorkerAvailable: checking signature %s' % signature_doc['_id'])

    # try for an exact  match on the signature's os_name, os_version, cpu_name
    # exact matches are by definition the best.
    startkey = [signature_doc["os_name"], signature_doc["os_version"], signature_doc["cpu_name"]]
    endkey   = [signature_doc["os_name"], signature_doc["os_version"], signature_doc["cpu_name"] + "\u9999"]

    matching_worker_id_rows = getMatchingWorkerIds(startkey=startkey, endkey=endkey)

    #debugMessage('isBetterWorkerAvailable: startkey: %s, endkey=%s, matching workers: %s' % (startkey, endkey, len(matching_worker_id_rows)))

    if len(matching_worker_id_rows) > 0:
        # workers are an exact match on os_name, os_version, cpu_name
        for matching_worker_id_doc in matching_worker_id_rows:
            #debugMessage("isBetterWorkerAvailable: checking worker %s" % matching_worker_id_doc["worker_id"])
            if this_worker_doc["_id"] == matching_worker_id_doc["worker_id"]:
                # this worker is the best available
                #debugMessage("isBetterWorkerAvailable: False. this worker %s is the best available." % this_worker_doc["_id"])
                return False
            if matching_worker_id_doc["worker_id"] in signature_doc["processed_by"]:
                # the worker already processed the signature and was the best.
                #debugMessage("isBetterWorkerAvailable: False. worker %s already processed signature and was the best available." % matching_worker_id_doc["worker_id"])
                return False
            #debugMessage("isBetterWorkerAvailable: True. worker %s has not processed signature and is the best available." % matching_worker_id_doc["worker_id"])
        return True


    # try a match on the signature's os_name, os_version
    startkey = [signature_doc["os_name"], signature_doc["os_version"]]
    endkey   = [signature_doc["os_name"], signature_doc["os_version"] + "\u9999"]

    matching_worker_id_rows = getMatchingWorkerIds(startkey=startkey, endkey=endkey)

    #debugMessage('isBetterWorkerAvailable: startkey: %s, endkey=%s, matching workers: %s' % (startkey, endkey, len(matching_worker_id_rows)))

    if len(matching_worker_id_rows) > 0:
        # workers are an exact match on os_name, os_version
        for matching_worker_id_doc in matching_worker_id_rows:
            #debugMessage("isBetterWorkerAvailable: checking worker %s" % matching_worker_id_doc["worker_id"])
            if this_worker_doc["_id"] == matching_worker_id_doc["worker_id"]:
                # this worker is the best available
                #debugMessage("isBetterWorkerAvailable: False. this worker %s is the best available." % this_worker_doc["_id"])
                return False
            if matching_worker_id_doc["worker_id"] in signature_doc["processed_by"]:
                #debugMessage("isBetterWorkerAvailable: False. worker %s already processed signature and was the best available." % matching_worker_id_doc["worker_id"])
                # the worker already processed the signature and was the best.
                return False
            #debugMessage("isBetterWorkerAvailable: True. worker %s has not processed signature and is the best available." % matching_worker_id_doc["worker_id"])
        return True

    # try a match on the signature's os_name
    startkey = [signature_doc["os_name"]]
    endkey   = [signature_doc["os_name"] + "\u9999"]

    matching_worker_id_rows = getMatchingWorkerIds(startkey=startkey, endkey=endkey)

    #debugMessage('isBetterWorkerAvailable: startkey: %s, endkey=%s, matching workers: %s' % (startkey, endkey, len(matching_worker_id_rows)))

    if len(matching_worker_id_rows) > 0:
        # workers are an exact match on os_name
        for matching_worker_id_doc in matching_worker_id_rows:
            #debugMessage("isBetterWorkerAvailable: checking worker %s" % matching_worker_id_doc["worker_id"])
            if this_worker_doc["_id"] == matching_worker_id_doc["worker_id"]:
                # this worker is the best available
                #debugMessage("isBetterWorkerAvailable: False. this worker %s is the best available." % this_worker_doc["_id"])
                return False
            if matching_worker_id_doc["worker_id"] in signature_doc["processed_by"]:
                # the worker already processed the signature and was the best.
                #debugMessage("isBetterWorkerAvailable: False. worker %s already processed signature and was the best available." % matching_worker_id_doc["worker_id"])
                return False
            #debugMessage("isBetterWorkerAvailable: True. worker %s has not processed signature and is the best available." % matching_worker_id_doc["worker_id"])
        return True

    # no matches for os. allow each worker a chance.
    # return True if there is a worker different from us
    # which has not yet processed the signature.
    #
    # this will cover the null signature/null os crash reports.

    # try a match on anything.
    startkey = [None]
    # need the leading ZZZZ for some reason.
    endkey   = ["ZZZZ\u9999"]

    matching_worker_id_rows = getMatchingWorkerIds(startkey=startkey, endkey=endkey)

    #debugMessage('isBetterWorkerAvailable: startkey: %s, endkey=%s, matching workers: %s' % (startkey, endkey, len(matching_worker_id_rows)))

    if len(matching_worker_id_rows) > 0:
        # workers do not match at all.
        for matching_worker_id_doc in matching_worker_id_rows:
            #debugMessage("isBetterWorkerAvailable: checking worker %s" % matching_worker_id_doc["worker_id"])
            if this_worker_doc["_id"] != matching_worker_id_doc["worker_id"] and matching_worker_id_doc["worker_id"] not in signature_doc["processed_by"]:
                return True

    return False

def freeOrphanJobs():

    signature_rows = getAllJobs()

    for signature_doc in signature_rows:
        worker_id    = signature_doc["worker"]
        signature_id = signature_doc["_id"]

        worker_doc = getDocument(worker_id)
        if not worker_doc:
            #debugMessage("freeOrphanJobs: job %s's worker %s is deleted." % (signature_id, worker_id))
            signature_doc["worker"] = None
            updateDocument(signature_doc)
        elif signature_id != worker_doc["signature_id"]:
            # double check that the signature has not changed it's worker
            temp_signature_doc = getDocument(signature_id)
            if not temp_signature_doc:
                #debugMessage("freeOrphanJobs: ignoring race condition: signature %s was deleted" % signature_id)
                pass
            elif temp_signature_doc["worker"] != worker_id:
                #debugMessage("freeOrphanJobs: ignoring race condition: signature %s's worker changed from %s to %s"
                #           % (signature_id, worker_id, temp_signature_doc["worker"]))
                pass
            else:
                #debugMessage("freeOrphanJobs: job %s's worker %s is working on %s." % (signature_id, worker_id, worker_doc["signature_id"]))
                signature_doc["worker"] = None
                updateDocument(signature_doc)

def checkSignatureForWorker(pending_job_rows):
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

    race_counter       = 0
    race_counter_limit = 10

    #debugMessage("checkSignatureForWorker: checking %d pending jobs" % len(pending_job_rows))

    for pending_job in pending_job_rows:
        try:
            race_counter += 1
            if race_counter > race_counter_limit:
                signature_doc = None
                break
            signature_id  = pending_job["signature_id"]
            #debugMessage("checkSignatureForWorker: checking signature %s" % signature_id)
            signature_doc = getDocument(signature_id)
            if not signature_doc or signature_doc["worker"]:
                #debugMessage("checkSignatureForWorker: race condition: someone else got the signature document %s" % signature_id)
                continue
        except KeyboardInterrupt:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            if str(exceptionValue) == 'WorkerInconsistent':
                raise

            logMessage('checkSignatureForWorker: ignoring getDocument(%s): exception: %s' %
                       (signature_id, formatException(exceptionType, exceptionValue, exceptionTraceback)))
            continue

        # update the signature and this worker as soon as possible
        # to cut down on race conditions when checking
        # signature_doc["worker"] <-> this_worker_doc["_id"].

        #debugMessage("checkSignatureForWorker: update signature %s's worker" % signature_id)

        try:
            signature_doc["worker"] = this_worker_doc["_id"]
            updateDocument(signature_doc)
        except KeyboardInterrupt:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if str(exceptionValue) != 'updateDocumentConflict':
                raise

            #debugMessage("checkSignatureForWorker: race condition updateDocumentConflict attempting to update signature document %s." % signature_id)
            continue

        #debugMessage("checkSignatureForWorker: update worker %s's signature" % this_worker_doc["_id"])

        try:
            this_worker_doc["signature_id"] = signature_id
            updateWorker(this_worker_doc)
        except KeyboardInterrupt:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            if str(exceptionValue) == 'WorkerInconsistent':
                raise

            if str(exceptionValue) != 'updateDocumentConfict':
                raise

            # should we get any non-fatal exception updating ourselves?
            raise

        # logically we might have checked this earlier but would
        # open ourselves to race conditions. Now that we have both
        # the signature and worker locked together we have the time
        # to check.

        #debugMessage("checkSignatureForWorker: check if we have processed signature %s" % signature_id)

        if this_worker_doc["_id"] in signature_doc["processed_by"]:

            #debugMessage("checkSignatureForWorker: we already processed signature %s" % signature_id)

            # We have already processed this signature document. Depending on the
            # population of workers, we were not the best at that time, but if we are
            # the best now, we can go ahead and delete it and try for the next job
            if isBetterWorkerAvailable(signature_doc):
                try:
                    # have to clear the signature's worker
                    #debugMessage("checkSignatureForWorker: there is a better worker available, removing signature's %s worker" % signature_id)
                    signature_doc["worker"] = None
                    updateDocument(signature_doc)
                except:
                    raise

            else:
                try:
                    #debugMessage("checkSignatureForWorker: there is not a better worker available, deleting signature %s" % signature_id)
                    deleteDocument(signature_doc)
                except:
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    if str(exceptionValue) != 'deleteDocumentConfict':
                        # throw other exceptions
                        raise
                    #debugMessage("checkSignatureForWorker: ignoring deleteDocumentConflict for signature %s" % signature_id)

            try:
                # have to clear the worker's signature
                #debugMessage("checkSignatureForWorker: clearing our signature %s" % signature_id)
                this_worker_doc["signature_id"] = None
                updateWorker(this_worker_doc)
            except:
                raise

            continue

        #debugMessage("checkSignatureForWorker: returning signature %s" % signature_doc["_id"])

        return signature_doc

    #debugMessage("checkSignatureForWorker: returning signature None")

    return None


def getSignatureForWorker():
    """
    return a signature unprocessed by this worker
    matches on priority, os_name, cpu_name, os_version
    or a subset of those properties by relaxing the right
    most condition until a match is found.
    """
    global this_worker_doc

    limit         = 50
    signature_doc = None

    for priority in ['0', '1']:
        startkey         = [priority, this_worker_doc["os_name"], this_worker_doc["cpu_name"], this_worker_doc["os_version"]]
        endkey           = [priority, this_worker_doc["os_name"], this_worker_doc["cpu_name"], this_worker_doc["os_version"] + '\u9999']
        pending_job_rows = getPendingJobs(startkey=startkey, endkey=endkey,limit=limit)
        signature_doc    = checkSignatureForWorker(pending_job_rows)
        if signature_doc:
            break

        startkey         = [priority, this_worker_doc["os_name"], this_worker_doc["cpu_name"]]
        endkey           = [priority, this_worker_doc["os_name"], this_worker_doc["cpu_name"] + '\u9999']
        pending_job_rows = getPendingJobs(startkey=startkey, endkey=endkey,limit=limit)
        signature_doc    = checkSignatureForWorker(pending_job_rows)
        if signature_doc:
            break

        startkey         = [priority, this_worker_doc["os_name"]]
        endkey           = [priority, this_worker_doc["os_name"] + '\u9999']
        pending_job_rows = getPendingJobs(startkey=startkey, endkey=endkey,limit=limit)
        signature_doc    = checkSignatureForWorker(pending_job_rows)
        if signature_doc:
            break

        startkey         = [priority]
        endkey           = [str(int(priority)+1)]
        pending_job_rows = getPendingJobs(startkey=startkey, endkey=endkey,limit=limit)
        signature_doc    = checkSignatureForWorker(pending_job_rows)
        if signature_doc:
            break

    #debugMessage("getSignatureForWorker: returning signature %s" % signature_doc)

    return signature_doc

def connectToDatabase():
    global db
    # attempt to access the database
    # keep trying until you succeed.
    messagequeue = []
    attempt = 0
    while True:
        try:
            db = couchquery.Database(dburi)
            dummy = db.views.signatures.workers(key=os.uname()[1])
            break
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            message = ('connectToDatabase: %s: %s, database %s not available, exception: %s' %
                       (os.uname()[1], getTimestamp(), dburi,
                        formatException(exceptionType, exceptionValue, exceptionTraceback)))
            messagequeue.append(message)
            print(message)

            if exceptionType == KeyboardInterrupt:
                raise

        time.sleep(60)
        attempt += 1

    if attempt > 0:
        for message in messagequeue:
            logMessage(message)
            time.sleep(1) # delay each message by a second to keep the log in order
        logMessage('connectToDatabase: attempt: %d, success connecting to %s' % (attempt, dburi))

    # this may take an arbitrary amount of time
    # so check if we have been deleted as a zombie.
    amIOk()

def createThisWorker(worker_comment, build_data):
    global this_worker_doc

    uname      = os.uname()
    os_name    = uname[0]
    host_name  = uname[1]
    os_version = uname[2]
    cpu_name   = uname[-1]

    if os_name.find("Linux") != -1:
        os_name = "Linux"
        os_version = re.search('([0-9]+\.[0-9]+\.[0-9]+).*', os_version).group(1)
    elif os_name.find("Darwin") != -1:
        os_name = "Mac OS X"
        proc = subprocess.Popen(["sw_vers"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout,stderr = proc.communicate()
        lines = stdout.split('\n')
        os_name = re.search('ProductName:\t(.*)', lines[0]).group(1)
        os_version = re.search('ProductVersion:\t([0-9]+\.[0-9]+).*', lines[1]).group(1)
    elif os_name.find("CYGWIN") != -1:
        os_name = "Windows NT"
        proc = subprocess.Popen(["cygcheck", "-s"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout,stderr = proc.communicate()
        lines = stdout.split('\r\n')
        os_version = re.search('.* Ver ([^ ]*) .*', lines[4]).group(1)
    else:
        raise Exception("invalid os_name: %s" % (os_name))

    bits = platform.architecture()[0]
    if cpu_name == "i386" or cpu_name == "i686":
        if bits == "32bit":
            cpu_name = "x86"
        elif bits == "64bit":
            cpu_name = "x86_64"

    worker_rows = getWorkers(key=host_name)

    if len(worker_rows) == 0:
        this_worker_doc = {"_id"          : host_name,
                           "type"         : "worker",
                           "os_name"      : os_name,
                           "os_version"   : os_version,
                           "cpu_name"     : cpu_name,
                           "comment"      : worker_comment,
                           "datetime"     : getTimestamp(),
                           "state"        : "new",
                           "signature_id" : None}


        # add build information to the worker document.
        for major_version in build_data:
            this_worker_doc[major_version] = {"builddate" : None, "changeset" : None }

        createDocument(this_worker_doc)

    else:
        this_worker_doc = worker_rows[0]

        this_worker_doc["_id"]          = host_name
        this_worker_doc["type"]         = "worker"
        this_worker_doc["os_name"]      = os_name
        this_worker_doc["os_version"]   = os_version
        this_worker_doc["cpu_name"]     = cpu_name
        this_worker_doc["comment"]      = worker_comment
        this_worker_doc["datetime"]     = getTimestamp()
        this_worker_doc["state"]        = "recycled"
        this_worker_doc["signature_id"] = None

        # add build information to the worker document if it isn't there already.
        for major_version in build_data:
            if not major_version in this_worker_doc:
                this_worker_doc[major_version] = {"builddate" : None, "changeset" : None }

        updateWorker(this_worker_doc)


def updateWorker(worker_doc):
    owned = (worker_doc["_id"] == this_worker_doc["_id"])

    if owned:
        amIOk()

    updateDocument(worker_doc, owned=owned)

def amIOk():
    """
    check our worker document against the database's version
    to make sure we are in sync, that the signature relationship is intact,
    and to see if we have been zombied or disabled.
    """
    global this_worker_doc

    if not this_worker_doc:
        # don't check out state if we haven't been initialized.
        return

    consistent         = True
    worker_id          = this_worker_doc["_id"]
    worker_state       = this_worker_doc["state"]
    signature_id       = this_worker_doc["signature_id"]

    try:
        curr_worker_doc = getDocument(worker_id)

        if not curr_worker_doc:
            # someone deleted our worker document in the database!
            logMessage("amIOk: worker %s was deleted by someone else." % worker_id)
            if signature_id:
                curr_signature_doc = getDocument(signature_id)
                if not curr_signature_doc or worker_id != curr_signature_doc["worker"]:
                    logMessage("amIOk: our signature document %s was deleted or is no longer owned by us: %s." % (signature_id, curr_signature_doc))
                    this_worker_doc["signature_id"] = None
                    consistent = False
            # XXX: do we need to change or remove the _rev property before re-inserting?
            createDocument(this_worker_doc)

        if this_worker_doc["_rev"] == curr_worker_doc["_rev"]:
            # our revisions match, so the database and the local
            # copy of our worker are in sync. Our signature doc
            # should exist and should point back to us.
            if signature_id:
                curr_signature_doc = getDocument(signature_id)
                if not curr_signature_doc:
                    logMessage("amIOk: worker %s's signature %s was deleted by someone else." % (worker_id, signature_id))
                    this_worker_doc["signature_id"] = None
                    this_worker_doc["state"] = "signature error"
                    updateDocument(this_worker_doc, owned=True)
                    consistent = False
                elif worker_id != curr_signature_doc["worker"]:
                    logMessage("amIOk: worker %s's signature %s was stolen by %s" % (worker_id, signature_id, curr_signature_doc["worker"]))
                    this_worker_doc["signature_id"] = None
                    this_worker_doc["state"] = "signature error"
                    updateDocument(this_worker_doc, owned=True)
                    consistent = False
        else:
            # our revisions differ, so someone else has updated
            # our worker document in the database. They could have
            # disabled us or zombied us and taken away our signature
            # or undisabled us.

            this_worker_doc["_rev"] = curr_worker_doc["_rev"]
            curr_worker_state       = curr_worker_doc["state"]

            if worker_state != "disabled" and curr_worker_state == "disabled":
                # we were disabled. free our signature if necessary.
                this_worker_doc["state"] = "disabled"
                consistent               = False

                logMessage("amIOk: worker %s was disabled." % worker_id)

                if signature_id:
                    curr_signature_doc = getDocument(signature_id)
                    if curr_signature_doc and worker_id == curr_signature_doc["worker"]:
                        logMessage("amIOk: worker %s freeing signature %s.." % (worker_id, signature_id))
                        curr_signature_doc["worker"] = None
                        updateDocument(curr_signature_doc, owned=True)
                    this_worker_doc["signature_id"] = None
                    updateDocument(this_worker_doc, owned=True)
            elif worker_state != "zombie" and curr_worker_state == "zombie":
                # we were zombied but are not dead!
                this_worker_doc["state"] = "undead"
                consistent               = False

                logMessage("amIOk: worker %s was zombied but is not dead." % worker_id)

                if signature_id:
                    # when zombied, our signature should have been taken away.
                    curr_signature_doc = getDocument(signature_id)
                    if curr_signature_doc and worker_id == curr_signature_doc["worker"]:
                        logMessage("amIOk: worker %s freeing signature %s.." % (worker_id, signature_id))
                        curr_signature_doc["worker"] = None
                        updateDocument(curr_signature_doc, owned=True)
                    this_worker_doc["signature_id"] = None
                    updateDocument(this_worker_doc, owned=True)
    except:
        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
        errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)
        logMessage('amIOk: worker: %s, exception: %s' % (worker_id, errorMessage))
        raise

    if not consistent:
        raise Exception('WorkerInconsistent')


def killZombies():
    """ zombify any *other* worker who has not updated status in zombie_time hours"""

    now          = datetime.datetime.now()
    deadinterval = datetime.timedelta(hours=zombie_time)
    worker_rows  = getAllWorkers()
    this_worker_id = this_worker_doc['_id']

    for worker_row in worker_rows:
        worker_row_id = worker_row['_id']

        if worker_row_id == this_worker_doc['_id']:
            # don't zombify ourselves
            continue

        if worker_row['state'] == 'disabled' or worker_row['state'] == 'zombie':
            # don't zombify disabled or zombified workers
            continue

        timestamp = convertTimestamp(worker_row['datetime'])

        if now - timestamp > deadinterval:
            logMessage("killZombies: worker %s zombifying %s (%s)" % (this_worker_id, worker_row_id, worker_row['datetime']))
            worker_row["state"] = "zombie"
            signature_id = worker_row['signature_id']
            if signature_id:
                worker_row['signature_id'] = None
                signature_doc = getDocument(signature_id)
                if signature_doc and worker_row_id == signature_doc['worker'] :
                    logMessage("killZombies: worker %s freeing zombie %s's signature %s.." % (this_worker_id, worker_row_id, signature_id))
                    signature_doc['worker'] = None
                    updateDocument(signature_doc)
            updateWorker(worker_row)

def doWork():
    global dburi

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
    (options, args) = parser.parse_args()

    dburi = options.databaseuri

    connectToDatabase()

    build_data = getBuildData()
    createThisWorker(options.worker_comment, build_data)
    logMessage('starting worker %s %s %s with program dated %s' %
               (this_worker_doc['os_name'], this_worker_doc['os_version'], this_worker_doc['cpu_name'],
                time.ctime(programModTime)))

    waittime = 0
    signature_doc = None

    checkup_interval = datetime.timedelta(minutes=5)
    last_checkup_time = datetime.datetime.now() - 2*checkup_interval

    while True:

        if datetime.datetime.now() - last_checkup_time > checkup_interval:
            checkForUpdate()
            checkDatabase()
            killZombies()
            freeOrphanJobs()
            last_checkup_time = datetime.datetime.now()

        sys.stdout.flush()
        time.sleep(waittime)
        waittime = 0

        if not signature_doc:
            signature_doc = getSignatureForWorker()
            if signature_doc:
                url_index     = 0
                major_version = signature_doc["major_version"]
                build_data    = getBuildData()
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
                waittime      = 60

                if this_worker_doc["state"] != "idle":
                    logMessage('No signatures available to proccess, going idle.')

                # XXX: right now we may need to update here to keep the worker alive
                # but when we have a worker heartbeat thread we can move these
                # updates to under the conditional above.
                this_worker_doc["state"]    = "idle"
                this_worker_doc["datetime"] = getTimestamp()
                updateWorker(this_worker_doc)

        elif (not this_worker_doc[major_version]["builddate"] or
              convertTimestamp(this_worker_doc[major_version]["builddate"]).day != datetime.date.today().day):

            this_worker_doc["state"]    = "building firefox %s %s" % (branch, buildtype)
            this_worker_doc["datetime"] = getTimestamp()
            updateWorker(this_worker_doc)

            buildstatus =  buildProduct("firefox", branch, buildtype)

            if buildstatus["success"]:
                this_worker_doc["state"]    = "success building firefox %s %s" % (branch, buildtype)
                this_worker_doc["datetime"] = getTimestamp()
                this_worker_doc[major_version]["builddate"] = getTimestamp()
                this_worker_doc[major_version]["changeset"] = buildstatus["changeset"]
                updateWorker(this_worker_doc)
            else:
                # wait for five minutes if a build failure occurs
                waittime = 300
                this_worker_doc["signature_id"] = None
                this_worker_doc["state"]        = "failure building firefox %s %s, clobbering..." % (branch, buildtype)
                this_worker_doc["datetime"]     = getTimestamp()
                this_worker_doc[major_version]["builddate"] = None
                this_worker_doc[major_version]["changeset"] = None
                updateWorker(this_worker_doc)
                # release the signature
                signature_doc["worker"]  = None
                updateDocument(signature_doc, owned=True)
                signature_doc = None
                clobberProduct("firefox", branch, buildtype)

        elif (this_worker_doc[major_version]["builddate"] and url_index < len(signature_doc["urls"])):

            url = signature_doc["urls"][url_index]

            if not checkIfUrlAlreadyTested(signature_doc, url_index):
                #debugMessage("testing firefox %s %s %s" % (branch, buildtype, url))
                this_worker_doc["state"]        = "testing firefox %s %s %s" % (branch, buildtype, url)
                this_worker_doc["datetime"]     = getTimestamp()
                updateWorker(this_worker_doc)
                try:
                    result = testUrl("firefox", branch, buildtype, url)
                    result["_id"]            = "%s_result_%05d" % (signature_doc["_id"], url_index)
                    result["worker_id"]      = this_worker_doc["_id"]
                    result["os_name"]        = this_worker_doc["os_name"]
                    result["os_version"]     = this_worker_doc["os_version"]
                    result["cpu_name"]       = this_worker_doc["cpu_name"]
                    result["major_version"]  = major_version
                    result["signature"]      = signature_doc["signature"]
                    result["bug_list"]       = signature_doc["bug_list"]
                    result["os_versionhash"] = signature_doc["os_versionhash"]
                    result["versionhash"]    = signature_doc["versionhash"]
                    result["major_versionhash"] = signature_doc["major_versionhash"]
                    result["changeset"]      = this_worker_doc[major_version]["changeset"]
                    result["datetime"]       = getTimestamp()
                    createDocument(result)
                    # if the signature was null, process all urls.
                    #if result["reproduced"] and signature_doc["signature"] != "\\N":
                    #    url_index = len(signature_doc["urls"])
                except:
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    if exceptionType == KeyboardInterrupt:
                        raise

                    errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)
                    logMessage("doWork: error in testUrl. %s signature: %s, url: %s, exception: %s" %
                               (exceptionValue, signature_doc["_id"], url, errorMessage))
            url_index += 1

        elif (url_index >= len(signature_doc["urls"])):

            if not isBetterWorkerAvailable(signature_doc):
                #debugMessage('doWork: no better worker available, deleting signature %s' % signature_doc['_id'])
                deleteDocument(signature_doc, owned=True)
            else:
                #debugMessage('doWork: better worker available, setting signature %s worker to None' % signature_doc['_id'])
                signature_doc["worker"] = None
                signature_doc["processed_by"][this_worker_doc["_id"]] = 1
                updateDocument(signature_doc, owned=True)

            signature_doc = None

            this_worker_doc["signature_id"] = None
            this_worker_doc["state"]        = 'completed signature'
            this_worker_doc["datetime"]     = getTimestamp()
            updateWorker(this_worker_doc)
        else:
            debugMessage('doWork: ?')


def checkDatabase():
    global database_status

    try:

        http = httplib2.Http()

        resp, content = http.request(dburi, method = 'GET')

        if resp['status'].find('2') != 0:
            logMessage('checkDatabase: GET %s bad response: %s, %s' % (dburi, resp, content))
        else:
            new_database_status = json.loads(content)

            if not database_status:
                database_status = new_database_status
            elif new_database_status['compact_running']:
                pass
            elif new_database_status['disk_size'] < database_status['disk_size']:
                database_status = new_database_status
            elif new_database_status['disk_size'] > 2 * database_status['disk_size']:
                logMessage('checkDatabase: compacting %s' % dburi)
                database_status = new_database_status
                time.sleep(5)
                resp, content = http.request(dburi + '/_compact', method='POST')
                if resp['status'].find('2') != 0:
                    logMessage('checkDatabase: POST %s/_compact response: %s, %s' % (dburi, resp, content))
                else:
                    time.sleep(5)
                    resp, content = http.request(dburi + '/_compact/signatures', method='POST')
                    if resp['status'].find('2') != 0:
                        logMessage('checkDatabase: POST %s/_compact/signatures response: %s, %s' % (dburi, resp, content))
                    else:
                        time.sleep(5)
                        resp, content = http.request(dburi + '/_view_cleanup', method='POST')
                        if resp['status'].find('2') != 0:
                            logMessage('checkDatabase: POST %s/_compact/_view_cleanup response: %s, %s' % (dburi, resp, content))
    except KeyboardInterrupt:
        raise
    except SystemExit:
        raise
    except:
        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

        errorMessage = formatException(exceptionType, exceptionValue, exceptionTraceback)

        # reconnect to the database in case it has dropped
        if re.search('conn_request', errorMessage):
            connectToDatabase()
            logMessage('checkDatabase: exception %s: %s' % (str(exceptionValue), formatException(exceptionType, exceptionValue, exceptionTraceback)))
        else:
            raise


def main():

    random.seed()

    exception_counter = 0

    while True:
        try:
            doWork()
        except:
            exception_counter += 1
            if exception_counter > 100:
                print "Too many errors. Terminating."
                exit(2)

            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            if exceptionType == SystemExit:
                break

            if exceptionType == KeyboardInterrupt:
                break

            if str(exceptionValue) == 'WorkerInconsistent':
                # If we were disabled, sleep for 5 minutes and check our state again.
                # otherwise restart.
                if this_worker_doc["state"] == "disabled":
                    while True:
                        time.sleep(300)
                        curr_worker_doc = getDocument(this_worker_doc["_id"])
                        if not curr_worker_doc:
                            # we were deleted. just terminate
                            exit(2)
                        if curr_worker_doc["state"] != "disabled":
                            this_worker_doc["state"] = "undisabled"
                            break

            logMessage('main: exception %s: %s' % (str(exceptionValue), formatException(exceptionType, exceptionValue, exceptionTraceback)))

            time.sleep(60)

    logMessage('terminating.')
    deleteDocument(this_worker_doc)

if __name__ == "__main__":
    main()

