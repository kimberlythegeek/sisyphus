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

import os
import stat
import time
import datetime
import sys
import subprocess
import re
import platform
import sets
import glob
import signal

sisyphus_dir     = os.environ["TEST_DIR"]
sys.path.append(os.path.join(sisyphus_dir,'bin'))

import sisyphus.utils
import sisyphus.couchdb
import sisyphus.bugzilla

class Worker():
    def __init__(self, worker_type, startdir, programPath, couchserveruri, testdbname, worker_comment, debug = False):

        def usr1_handler(signum, frame):
            # catch usr1 signal and terminate.
            # used when profiling to obtain a clean shutdown.
            exit(0)

        signal.signal(signal.SIGUSR1, usr1_handler)

        self.worker_type    = worker_type
        self.startdir       = startdir
        self.programPath    = programPath
        self.programModTime = os.stat(programPath)[stat.ST_MTIME]
        self.zombie_time    = 6 # if a worker hasn't updated datetime in zombie_time hours, it will be killed.

        urimatch = re.search('(https?:)(.*)', couchserveruri)
        if not urimatch:
            raise Exception('Bad database uri')

        self.testdburi       = couchserveruri + '/' + testdbname
        self.testdb          = sisyphus.couchdb.Database(self.testdburi)
        self.debug           = debug
        self.testdb.debug    = debug

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
            #os_name = re.search('ProductName:\t(.*)', lines[0]).group(1)
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
        elif cpu_name == 'Power Macintosh':
            cpu_name = 'ppc'

        worker_doc = self.testdb.getDocument(host_name)
        branches_doc = self.testdb.getDocument('branches')

        branches = branches_doc['branches']

        if not worker_doc:
            self.document = {
                "_id"          : host_name,
                "type"         : "worker_" + worker_type,
                "os_name"      : os_name,
                "os_version"   : os_version,
                "cpu_name"     : cpu_name,
                "comment"      : worker_comment,
                "datetime"     : sisyphus.utils.getTimestamp(),
                "state"        : "new"
                }


            # add build information to the worker document.
            for branch in branches:
                self.document[branch] = {
                    "builddate"       : None,
                    "buildsuccess"    : None,
                    "changeset"       : None,
                    "executablepath"  : None,
                    "packagesuccess"  : None,
                    "clobbersuccess"  : None,
                    "uploadsuccess"   : None
                    }

            self.testdb.createDocument(self.document)

        else:
            self.document = worker_doc

            self.document["_id"]          = host_name
            self.document["type"]         = "worker_" + worker_type
            self.document["os_name"]      = os_name
            self.document["os_version"]   = os_version
            self.document["cpu_name"]     = cpu_name
            self.document["comment"]      = worker_comment
            self.document["datetime"]     = sisyphus.utils.getTimestamp()
            self.document["state"]        = "recycled"

            # add build information to the worker document if it isn't there already.
            for branch in branches:
                if not branch in self.document:
                    self.document[branch] = {
                        "builddate"       : None,
                        "buildsuccess"    : None,
                        "changeset"       : None,
                        "executablepath"  : None,
                        "packagesuccess"  : None,
                        "clobbersuccess"  : None,
                        "uploadsuccess"   : None
                        }

            self.updateWorker(self.document)

    def logMessage(self, msg, reconnect = True):
        self.testdb.logMessage(msg, reconnect)

    def debugMessage(self, msg):
        self.testdb.debugMessage(msg)

    def reloadProgram(self):
        sys.stdout.flush()
        newargv = sys.argv
        newargv.insert(0, sys.executable)
        os.chdir(self.startdir)
        os.execvp(sys.executable, newargv)

    def checkForUpdate(self, job_doc = None):
        # Note this will restart the program leaving the self.document
        # in the database where it will be picked up on restart
        # preserving the most recent build data.
        #
        # required globals:
        #
        # startdir       = os.getcwd()
        # programPath    = os.path.abspath(os.path.join(os.path.realpath(os.path.dirname(sys.argv[0])), os.path.basename(sys.argv[0])))
        #
        if os.stat(self.programPath)[stat.ST_MTIME] != self.programModTime:
            message = 'checkForUpdate: Program change detected. Reloading from disk. %s %s' % (sys.executable, sys.argv)
            self.testdb.logMessage(message)
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

    def extractBugzillaBugList(self, bug_list, bugzilla_content):
        # reusing cached data while adding new data from the
        # last 7 days can result in bugs which have been fixed
        # being added to the closed list while they remain in
        # the open list. Therefore when adding a bug to one
        # resolution, be sure to delete it from the other.

        def cmp_bug_numbers(lbug, rbug):
            return int(lbug) - int(rbug)

        if 'bugs' in bugzilla_content:
            for bug in bugzilla_content['bugs']:
                if bug['resolution']:
                    this_resolution = 'closed'
                    that_resolution = 'open'
                else:
                    this_resolution = 'open'
                    that_resolution = 'closed'

                bug_list[this_resolution].append(bug['id'])
                try:
                    del bug_list[that_resolution][bug_list[that_resolution].index(bug['id'])]
                except ValueError:
                    pass

        # uniqify and sort the bug_list
        for state in 'open', 'closed':
            bug_list[state] = list(sets.Set(bug_list[state]))
            bug_list[state].sort(cmp_bug_numbers)

        return bug_list

    def clean_url_list(self, url_list):
        exclude_urls_set = sets.Set(['startup', 'shutdown', 'automationutils.processLeakLog()', 'a blank page'])
        url_set = sets.Set(url_list)
        url_set.difference_update(exclude_urls_set)
        return list(url_set)

    def update_bug_list_assertions(self, product, branch, buildtype, os_name, os_version, cpu_name, timestamp, assertionmessage, assertionfile, assertionurl_list):
        """
        This method can be called either when a new assertion is being
        processed or when updating the bug_list in the history
        database.

        If it is called for a new assertion, timestamp is the datetime
        field from the result_assertion document and will be used to
        update the firstdatetime and lastdatetime fields in the
        history assertion document and may be used when creating a new
        history assertion document.

        However, if it is called to update the bug history, then the
        history assertion document is guaranteed to already exist and the
        timestamp will None and will not be used to update the
        firstdatetime or lastdatetime in the history assertion document.

        """

        self.debugMessage('update_bug_list_assertions: start: %s %s %s' % (assertionmessage, assertionfile, assertionurl_list))

        bug_list           = None
        now                = datetime.datetime.now()

        history_assertions = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                          startkey=["history_assertion", assertionmessage, assertionfile,
                                                    product, branch, buildtype, os_name, os_version, cpu_name],
                                          endkey=["history_assertion", assertionmessage, assertionfile,
                                                  product, branch, buildtype, os_name, os_version, cpu_name + "\u9999"],
                                          include_docs=True)

        if len(history_assertions) > 0:

            history_assertion  = history_assertions[0]
            if timestamp is None:
                timestamp          = history_assertion["firstdatetime"]
            if "bug_list" not in history_assertion:
                history_assertion["bug_list"] = None
            bug_list           = history_assertion["bug_list"]
            history_updatetime = sisyphus.utils.convertTimestamp(history_assertion["updatetime"])
            history_stale      = (history_updatetime < now - datetime.timedelta(days=1))
            bug_age            = 7

            if not bug_list: # shouldn't be needed, but just in case db is not correct...
                history_stale = True

            if len(history_assertions) > 1:
                self.logMessage("update_bug_list_assertions: deleting %d duplicates %s %s from history" %
                                (len(history_assertions) - 1, assertionmessage, assertionfile))
                iassertion = 1
                lassertion = len(history_assertions)
                while iassertion < lassertion:
                    try:
                        # We can have update conflicts if the update bug history is currently running
                        # on another worker. Just ignore them but pass through any other exceptions.
                        self.testdb.deleteDocument(history_assertions[iassertion])
                    except KeyboardInterrupt:
                        raise
                    except SystemExit:
                        raise
                    except:
                        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                        errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                        if not re.search('deleteDocumentConflict', str(exceptionValue)):
                            raise

                    iassertion += 1

        else:
            # there is no historical assertion with an exact match
            # we need to create a new one.
            history_assertion = {
                "type"            : "history_assertion",
                "product"         : product,
                "branch"          : branch,
                "buildtype"       : buildtype,
                "os_name"         : os_name,
                "os_version"      : os_version,
                "cpu_name"        : cpu_name,
                "firstdatetime"   : timestamp,
                "lastdatetime"    : timestamp,
                "assertion"       : assertionmessage,
                "assertionfile"   : assertionfile,
                "updatetime"      : timestamp,
                "location_id_list" : [],
                "bug_list"        : None,
                "suppress"        : False
                }
            history_stale  = True
            bug_age        = None

            # since the bug list does not depend on the full key
            # try to get a matching assertion using just the assertionmessage.

            history_assertions = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                              startkey=["history_assertion", assertionmessage],
                                              endkey=["history_assertion", assertionmessage + "\u9999"],
                                              include_docs=True)

            if len(history_assertions) > 0:
                for cache in history_assertions:
                    if cache["bug_list"]:
                        break
                if cache["bug_list"]:
                    history_assertion["bug_list"]   = cache["bug_list"]
                    history_assertion["updatetime"] = cache["updatetime"]
                    bug_age  = 7
                    bug_list = cache["bug_list"]

            try:
                self.testdb.createDocument(history_assertion)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        assertionurl_list = self.clean_url_list(assertionurl_list)
        assertionurl_set = sets.Set(assertionurl_list)
        location_id_set  = sets.Set(history_assertion["location_id_list"])

        if not assertionurl_set.issubset(location_id_set):
            # assertionurl_list contains new urls
            history_stale = True

        if history_stale and assertionmessage:

            # We do not have a bug_list yet, or the assertion was last updated over a day ago.
            # Look up any bugs that match this assertion

            if not bug_list:
                bug_age = None # need to do a full bugzilla search the first time.
                bug_list = {'open' : [], 'closed' : []}

            if len(assertionurl_list) > 0:
                assertionurls = ' '.join(assertionurl_list)
                self.debugMessage('update_bug_list_assertions: begin searchBugzillaUrls: %s %s' % (assertionurls, bug_age))
                resp, content = sisyphus.bugzilla.searchBugzillaUrls(assertionurls, 'contains_any', None, bug_age)
                self.debugMessage('update_bug_list_assertions: end   searchBugzillaUrls: %s %s' % (assertionurls, bug_age))
                if 'bugs' in content:
                    bug_list = self.extractBugzillaBugList(bug_list, content)

            self.debugMessage('update_bug_list_assertions: begin searchBugzillaText: %s %s' % (assertionmessage, bug_age))
            resp, content = sisyphus.bugzilla.searchBugzillaText(assertionmessage, 'contains', None, bug_age)
            self.debugMessage('update_bug_list_assertions: end   searchBugzillaText: %s %s' % (assertionmessage, bug_age))

            if 'bugs' in content:
                bug_list = self.extractBugzillaBugList(bug_list, content)

        # Check if the firstdatetime-lastdatetime range should be updated
        # and force an update if necessary.
        if not history_assertion["firstdatetime"] or timestamp < history_assertion["firstdatetime"]:
            history_assertion["firstdatetime"] = timestamp
            history_stale = True
        if not history_assertion["lastdatetime"] or timestamp > history_assertion["lastdatetime"]:
            history_assertion["lastdatetime"] = timestamp
            history_stale = True

        if history_stale:
            history_assertion["location_id_list"].extend(assertionurl_list)
            # uniqify the location id list.
            history_assertion["location_id_list"] = list(sets.Set(history_assertion["location_id_list"]))
            history_assertion["location_id_list"].sort()
            history_assertion["bug_list"]     = bug_list
            history_assertion["updatetime"]   = sisyphus.utils.getTimestamp()
            try:
                self.testdb.updateDocument(history_assertion, True)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        self.debugMessage('update_bug_list_assertions: end %s' % bug_list)


    def process_assertions(self, result_id, product, branch, buildtype, timestamp, assertion_list, location_id, test, extra_test_args):

        def cmp_assertion(lassertion, rassertion):
            lkey = lassertion["message"] + ':' + lassertion["file"]
            rkey = rassertion["message"] + ':' + rassertion["file"]
            if lkey < rkey:
                return -1
            if lkey > rkey:
                return +1
            return 0

        assertion_list.sort(cmp_assertion)

        os_name              = self.document["os_name"]
        os_version           = self.document["os_version"]
        cpu_name             = self.document["cpu_name"]
        count                = 0
        lastkey              = None
        result_assertion_doc = None

        for assertion in assertion_list:
            assertionmessage = assertion["message"]
            assertionfile    = assertion["file"]
            currkey = assertionmessage + ":" + assertionfile

            if result_assertion_doc and lastkey and lastkey != currkey:
                result_assertion_doc["count"] = count
                self.testdb.createDocument(result_assertion_doc)
                result_assertion_doc = None
                count = 0

            elif result_assertion_doc is None:

                self.update_bug_list_assertions(product, branch, buildtype,
                                                os_name, os_version, cpu_name,
                                                timestamp, assertionmessage, assertionfile, [location_id])

                result_assertion_doc = {
                    "type"            : "result_assertion",
                    "result_id"       : result_id,
                    "product"         : product,
                    "branch"          : branch,
                    "buildtype"       : buildtype,
                    "test"            : test,
                    "extra_test_args" : extra_test_args,
                    "os_name"         : os_name,
                    "os_version"      : os_version,
                    "cpu_name"        : cpu_name,
                    "worker_id"       : self.document["_id"],
                    "datetime"        : timestamp,
                    "assertion"       : assertionmessage,
                    "assertionfile"   : assertionfile,
                    "location_id"     : location_id,
                    "updatetime"      : timestamp,
                    "bug"             : "",
                    "comment"         : ""
                    }

            count  += 1
            lastkey = currkey

        if result_assertion_doc:
            result_assertion_doc["count"] = count
            self.testdb.createDocument(result_assertion_doc, True)

    def parse_valgrind(self, valgrind_text):
        """
        Parse the valgrind messages text and return a list
        of individual messages.
        """

        reValgrindLeader     = re.compile(r'==[0-9]+==')
        reValgrindParseLeader = re.compile(r'==[0-9]+==[^\n]*\n', re.MULTILINE)
        reValgrindParseOther = re.compile(r'(==[0-9]+==\s\S[^\n]*\n)(==[0-9]+==\s\S[^\n]*\n)+?(?:==[0-9]+==\n)', re.MULTILINE)
        reValgrindParseBlock = re.compile(r'(==[0-9]+==\s\S[^\n]*\n)(==[0-9]+==\s{2,}\S[^\n]*\n)+?(?:==[0-9]+==\n)', re.MULTILINE)
        reLine               = re.compile(r'.*')
        reNumbers            = re.compile(r'[0-9]+', re.MULTILINE)
        reHexNumbers         = re.compile(r'0x[0-9a-fA-F]+', re.MULTILINE)

        valgrind_list = []

        while len(valgrind_text) > 0:
            match = reValgrindParseBlock.match(valgrind_text)
            if not match:
                # didn't match a complete memcheck valgrind block
                # try to match and skip a valgrind message block of the form
                # ==999== message
                # ==999== message
                # ==999==
                match = reValgrindParseOther.match(valgrind_text)
                if match:
                    valgrind_text = valgrind_text[len(match.group(0)):]
                    continue
                # didn't match a message block.
                # try to match and skip a single valgrind message line of the form
                # ==999==.*
                match = reValgrindParseLeader.match(valgrind_text)
                if match:
                    valgrind_text = valgrind_text[len(match.group(0)):]
                    continue
                newlinepos = valgrind_text.find('\n')
                if newlinepos != -1:
                    valgrind_text = valgrind_text[newlinepos + 1:]
                    continue
                break

            valgrind_data = match.group(0)
            valgrind_data = re.sub(reValgrindLeader, '', valgrind_data)
            line_match    = reLine.match(valgrind_data)
            valgrind_msg  = line_match.group(0)

            # create a valgrind signature by replacing line numbers, hex numbers with
            # spaces for searching bugzilla with all strings query type, and taking the first
            # three lines.
            valgrind_signature = ' '.join(valgrind_data.split('\n')[0:3])
            valgrind_signature = re.sub(reHexNumbers, '', valgrind_signature)
            valgrind_signature = re.sub(reNumbers, '', valgrind_signature)
            valgrind_signature = re.sub('\W+', ' ', valgrind_signature)
            valgrind_signature = re.sub(' {2,}', ' ', valgrind_signature)

            if not re.search('^HEAP', valgrind_signature):
                valgrind = {
                    "message"   : valgrind_msg.strip(),
                    "data"      : valgrind_data.strip(),
                    "signature" : valgrind_signature.strip(),
                    }
                valgrind_list.append(valgrind)
            valgrind_text = valgrind_text[len(match.group(0)):]

        return valgrind_list

    def update_bug_list_valgrinds(self, product, branch, buildtype, os_name, os_version, cpu_name, timestamp, valgrindmessage, valgrindsignature, valgrindurl_list):
        """
        This method can be called either when a new valgrind is being
        processed or when updating the bug_list in the history
        database.

        If it is called for a new valgrind, timestamp is the datetime
        field from the result_valgrind document and will be used to
        update the firstdatetime and lastdatetime fields in the
        history valgrind document and may be used when creating a new
        history valgrind document.

        However, if it is called to update the bug history, then the
        history valgrind document is guaranteed to already exist and the
        timestamp will None and will not be used to update the
        firstdatetime or lastdatetime in the history valgrind document.

        """

        self.debugMessage('update_bug_list_valgrinds: start: %s %s %s' % (valgrindmessage, valgrindsignature, valgrindurl_list))

        bug_list           = None
        now                = datetime.datetime.now()

        history_valgrinds = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                         startkey=["history_valgrind", valgrindmessage, valgrindsignature,
                                                   product, branch, buildtype, os_name, os_version, cpu_name],
                                         endkey=["history_valgrind", valgrindmessage, valgrindsignature,
                                                 product, branch, buildtype, os_name, os_version, cpu_name + "\u9999"],
                                         include_docs=True)

        if len(history_valgrinds) > 0:

            history_valgrind   = history_valgrinds[0]
            if timestamp is None:
                timestamp          = history_valgrind["firstdatetime"]
            if "bug_list" not in history_valgrind:
                history_valgrind["bug_list"] = None
            bug_list           = history_valgrind["bug_list"]
            history_updatetime = sisyphus.utils.convertTimestamp(history_valgrind["updatetime"])
            history_stale      = (history_updatetime < now - datetime.timedelta(days=1))
            bug_age            = 7

            if not bug_list: # shouldn't be needed, but just in case db is not correct...
                history_stale = True

            if len(history_valgrinds) > 1:
                self.logMessage("update_bug_list_valgrinds: deleting %d duplicates %s %s from history" %
                                (len(history_valgrinds) - 1, valgrindmessage, valgrindsignature))
                ivalgrind = 1
                lvalgrind = len(history_valgrinds)
                while ivalgrind < lvalgrind:
                    try:
                        # We can have update conflicts if the update bug history is currently running
                        # on another worker. Just ignore them but pass through any other exceptions.
                        self.testdb.deleteDocument(history_valgrinds[ivalgrind])
                    except KeyboardInterrupt:
                        raise
                    except SystemExit:
                        raise
                    except:
                        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                        errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                        if not re.search('deleteDocumentConflict', str(exceptionValue)):
                            raise

                    ivalgrind += 1

        else:
            # there is no historical valgrind with an exact match
            # we need to create a new one.
            history_valgrind = {
                "type"            : "history_valgrind",
                "product"         : product,
                "branch"          : branch,
                "buildtype"       : buildtype,
                "os_name"         : os_name,
                "os_version"      : os_version,
                "cpu_name"        : cpu_name,
                "firstdatetime"   : timestamp,
                "lastdatetime"    : timestamp,
                "valgrind"        : valgrindmessage,
                "valgrindsignature" : valgrindsignature,
                "location_id_list" : [],
                "updatetime"      : timestamp,
                "bug_list"        : None,
                "suppress"        : False
                }
            history_stale = True
            bug_age       = None

            # since the bug list does not depend on the full key
            # try to get a matching valgrind using just the valgrindmessage
            # and valgrindsignature.

            history_valgrinds = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                             startkey=["history_valgrind", valgrindmessage, valgrindsignature],
                                             endkey=["history_valgrind", valgrindmessage, valgrindsignature + "\u9999"],
                                             include_docs=True)

            if len(history_valgrinds) > 0:
                for cache in history_valgrinds:
                    if cache["bug_list"]:
                        break
                if cache["bug_list"]:
                    history_valgrind["bug_list"]   = cache["bug_list"]
                    history_valgrind["updatetime"] = cache["updatetime"]
                    bug_age  = 7
                    bug_list = cache["bug_list"]

            try:
                self.testdb.createDocument(history_valgrind)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        valgrindurl_list = self.clean_url_list(valgrindurl_list)
        valgrindurl_set = sets.Set(valgrindurl_list)
        location_id_set  = sets.Set(history_valgrind["location_id_list"])

        if not valgrindurl_set.issubset(location_id_set):
            # valgrindurl_list contains new urls
            history_stale = True

        if history_stale and valgrindsignature:

            # We do not have a bug_list yet, or the valgrind was last updated over a day ago.
            # Look up any bugs that match this valgrind

            if not bug_list:
                bug_age = None # need to do a full bugzilla search the first time.
                bug_list = {'open' : [], 'closed' : []}

            if len(valgrindurl_list) > 0:
                valgrindurls = ' '.join(valgrindurl_list)
                self.debugMessage('update_bug_list_valgrinds: begin searchBugzillaUrls: %s %s' % (valgrindurls, bug_age))
                resp, content = sisyphus.bugzilla.searchBugzillaUrls(valgrindurls, 'contains_any', None, bug_age)
                self.debugMessage('update_bug_list_valgrinds: end   searchBugzillaUrls: %s %s' % (valgrindurls, bug_age))
                if 'bugs' in content:
                    bug_list = self.extractBugzillaBugList(bug_list, content)

            self.debugMessage('update_bug_list_valgrinds: begin searchBugzillaText: %s %s' % (valgrindsignature, bug_age))
            resp, content = sisyphus.bugzilla.searchBugzillaText(valgrindsignature, 'contains_all', None, bug_age)
            self.debugMessage('update_bug_list_valgrinds: end   searchBugzillaText: %s %s' % (valgrindsignature, bug_age))

            if 'bugs' in content:
                bug_list = self.extractBugzillaBugList(bug_list, content)

        # Check if the firstdatetime-lastdatetime range should be updated
        # and force an update if necessary.
        if not history_valgrind["firstdatetime"] or timestamp < history_valgrind["firstdatetime"]:
            history_valgrind["firstdatetime"] = timestamp
        if not history_valgrind["lastdatetime"] or timestamp > history_valgrind["lastdatetime"]:
            history_valgrind["lastdatetime"] = timestamp

        if history_stale:
            history_valgrind["location_id_list"].extend(valgrindurl_list)
            # uniqify the location id list.
            history_valgrind["location_id_list"] = list(sets.Set(history_valgrind["location_id_list"]))
            history_valgrind["location_id_list"].sort()
            history_valgrind["bug_list"]     = bug_list
            history_valgrind["updatetime"]   = sisyphus.utils.getTimestamp()
            try:
                self.testdb.updateDocument(history_valgrind, True)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        self.debugMessage('update_bug_list_valgrinds: end %s' % bug_list)


    def process_valgrind(self, result_id, product, branch, buildtype, timestamp, valgrind_list, location_id, test, extra_test_args):

        def cmp_valgrind(lvalgrind, rvalgrind):
            lkey = lvalgrind["message"] + ':' + lvalgrind["signature"]
            rkey = rvalgrind["message"] + ':' + rvalgrind["signature"]
            if lkey < rkey:
                return -1
            if lkey > rkey:
                return +1
            return 0

        valgrind_list.sort(cmp_valgrind)

        os_name              = self.document["os_name"]
        os_version           = self.document["os_version"]
        cpu_name             = self.document["cpu_name"]
        count                = 0
        lastkey              = None
        result_valgrind_doc  = None

        for valgrind in valgrind_list:
            valgrindmessage   = valgrind["message"]
            valgrindsignature = valgrind["signature"]
            valgrinddata      = valgrind["data"]

            if valgrindsignature.find('HEAP SUMMARY') == 0:
                continue

            currkey = valgrindmessage + ":" + valgrindsignature

            if result_valgrind_doc and lastkey and lastkey != currkey:
                result_valgrind_doc["count"] = count
                self.testdb.updateDocument(result_valgrind_doc, True)
                result_valgrind_doc = None
                count = 0

            elif result_valgrind_doc is None:

                self.update_bug_list_valgrinds(product, branch, buildtype,
                                               os_name, os_version, cpu_name,
                                               timestamp, valgrindmessage, valgrindsignature, [location_id])

                result_valgrind_doc = {
                    "type"            : "result_valgrind",
                    "result_id"       : result_id,
                    "product"         : product,
                    "branch"          : branch,
                    "buildtype"       : buildtype,
                    "test"            : test,
                    "extra_test_args" : extra_test_args,
                    "os_name"         : os_name,
                    "os_version"      : os_version,
                    "cpu_name"        : cpu_name,
                    "worker_id"       : self.document["_id"],
                    "datetime"        : timestamp,
                    "valgrind"        : valgrindmessage,
                    "valgrindsignature" : valgrindsignature,
                    "valgrinddata"    : valgrinddata,
                    "location_id"     : location_id,
                    "updatetime"      : timestamp,
                    "bug"             : "",
                    "comment"         : ""
                    }
                self.testdb.createDocument(result_valgrind_doc)

            count  += 1
            lastkey = currkey

        if result_valgrind_doc:
            result_valgrind_doc["count"] = count
            self.testdb.updateDocument(result_valgrind_doc, True)

    def parse_crashreport(self, crashreport):
        """
        Parse the crash report and report interesting stuff

        Format:

        Operating system: Mac OS X
                          10.5.8 9L30
        CPU: x86
             GenuineIntel family 6 model 23 stepping 6
             2 CPUs

        Crash reason:  EXC_BAD_ACCESS / KERN_PROTECTION_FAILURE
        Crash address: 0x4

        Thread 0 (crashed)
         0  XUL!nsThebesFontMetrics::GetMetrics() const [nsThebesFontMetrics.cpp : 117 + 0x26]
            eip = 0x040cb2e6   esp = 0xbfff77c0   ebp = 0xbfff77d8   ebx = 0x040cbc54
            esi = 0x063b1338   edi = 0x0000b478   eax = 0x00000004   ecx = 0x0473d654
            edx = 0x00000004   efl = 0x00210286
            Found by: given as instruction pointer in context
         1  XUL!nsThebesFontMetrics::GetExternalLeading(int&) [nsThebesFontMetrics.cpp : 195 + 0xa]
            eip = 0x040cbc60   esp = 0xbfff77e0   ebp = 0xbfff7808
            Found by: previous frame's frame pointer
         2  XUL!_ZL19GetNormalLineHeightP14nsIFontMetrics [nsHTMLReflowState.cpp : 2078 + 0x18]
            eip = 0x034402b8   esp = 0xbfff7810   ebp = 0xbfff7858
            Found by: previous frame's frame pointer
         3  XUL!_ZL17ComputeLineHeightP14nsStyleContexti [nsHTMLReflowState.cpp : 2128 + 0x12]
            eip = 0x03440520   esp = 0xbfff7860   ebp = 0xbfff78a8
            Found by: previous frame's frame pointer

        The first Thread line will be the crasher.
        Interesting stuff to pull out:

        Crash reason   : EXC_BAD_ACCESS / KERN_PROTECTION_FAILURE
        Crash address  : 0x4
        Thread number  : 0
        Signature      : nsThebesFontMetrics::GetMetrics()
        Stack          : nsThebesFontMetrics::GetMetrics() nsThebesFontMetrics::GetExternalLeading(int&) ...

        """

        reReason     = re.compile(r'Crash reason:\s+(.*)')
        reAddress    = re.compile(r'Crash address:\s+(.*)')
        reThread     = re.compile(r'Thread ([0-9]+) [(]crashed[)]')
        reFrameDecl  = re.compile(r'\s([0-9]+)\s+([^)]+[)]).*')
        reFrameOff   = re.compile(r'\s([0-9]+)\s+([^\[]*).*')
        reason       = None
        address      = None
        thread       = None
        message      = None
        signature    = None
        frames       = []
        frames_max   = 4
        reNumbers    = re.compile(r'[0-9]+', re.MULTILINE)
        reHexNumbers = re.compile(r'0x[0-9a-fA-F]+', re.MULTILINE)

        message      = ''
        signature    = ''

        report_lines = crashreport.split('\n')

        for line in report_lines:
            if reason is None:
                match = reReason.match(line)
                if match:
                    reason = match.group(1)

            if address is None:
                match = reAddress.match(line)
                if match:
                    address = match.group(1)

            if thread is None:
                match = reThread.match(line)
                if match:
                    thread = match.group(1)
            elif not line:
                break
            else:
                match = reFrameDecl.match(line)
                if not match:
                    match = reFrameOff.match(line)
                if match:
                    frame_number = match.group(1)
                    frame_text   = match.group(2)
                    frame_text   = re.sub(' \+ ', '@', frame_text) # foo.dll + 0x1234 => foo.dll@0x1234
                    frame_text   = re.sub('\s*[^\s]*[!]', ' ', frame_text) # foo!bar => bar
                    frame_text   = re.sub('\s\[[^\]]*\]\s*', ' ', frame_text) # foo [bar] => foo
                    frame_text   = re.sub('[(][^)]*[)]', '', frame_text)    # foo(bar) => foo
                    frame_text   = re.sub('\s+', ' ', frame_text)
                    frame_text   = frame_text.strip()
                    frames.append({'number': frame_number, 'text': frame_text})
                    if len(frames) > frames_max:
                        break

        if len(frames) > 0:
            message   = frames[0]['text']
            signature = ''
            for frame in frames:
                signature += ' ' + frame['text']
            message = message.strip()
            signature = signature.strip()
            if re.search('^0x[0-9a-fA-F]+$', message):
                # top frame is a pure address. pull in next frame.
                # in format address | frame
                topframe_list = signature.replace('Flash Player', 'Flash_Player').split(' ')
                if len(topframe_list) > 1:
                    message  = topframe_list[0] + ' | ' + topframe_list[1].replace('Flash_Player', 'Flash Player')

        return {'reason' : reason, 'address' : address, 'thread' : thread, 'message' : message, 'signature' : signature}

    def update_bug_list_crashreports(self, product, branch, buildtype, os_name, os_version, cpu_name, timestamp, crashmessage, crashsignature, crashurl_list):
        """

        This method can be called either when a new crash is being
        processed or when updating the bug_list in the history
        database.

        If it is called for a new crash, timestamp is the datetime
        field from the result_crash document and will be used to
        update the firstdatetime and lastdatetime fields in the
        history crash document and may be used when creating a new
        history crash document.

        However, if it is called to update the bug history, then the
        history crash document is guaranteed to already exist and the
        timestamp will None and will not be used to update the
        firstdatetime or lastdatetime in the history crash document.

        """

        self.debugMessage('update_bug_list_crashreports: start: %s %s %s' % (crashmessage, crashsignature, crashurl_list))

        bug_list           = None
        now                = datetime.datetime.now()

        history_crashes = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                       startkey=["history_crash", crashmessage, crashsignature,
                                                 product, branch, buildtype, os_name, os_version, cpu_name],
                                       endkey=["history_crash", crashmessage, crashsignature,
                                               product, branch, buildtype, os_name, os_version, cpu_name + "\u9999"],
                                       include_docs=True)

        if len(history_crashes) > 0:

            history_crash      = history_crashes[0]
            if timestamp is None:
                timestamp          = history_crash["firstdatetime"]
            if "bug_list" not in history_crash:
                history_crash["bug_list"] = None
            bug_list           = history_crash["bug_list"]
            history_updatetime = sisyphus.utils.convertTimestamp(history_crash["updatetime"])
            history_stale      = (history_updatetime < now - datetime.timedelta(days=1))
            bug_age            = 7

            if not bug_list: # shouldn't be needed, but just in case db is not correct...
                history_stale = True

            if len(history_crashes) > 1:
                self.logMessage("update_bug_list_crashreports: deleting %d duplicates %s %s from history" %
                                (len(history_crashes) - 1, crashmessage, crashsignature))
                icrash = 1
                lcrash = len(history_crashes)
                while icrash < lcrash:
                    try:
                        # We can have update conflicts if the update bug history is currently running
                        # on another worker. Just ignore them but pass through any other exceptions.
                        self.testdb.deleteDocument(history_crashes[icrash])
                    except KeyboardInterrupt:
                        raise
                    except SystemExit:
                        raise
                    except:
                        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                        errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                        if not re.search('deleteDocumentConflict', str(exceptionValue)):
                            raise

                    icrash += 1

        else:
            # there is no historical crash with an exact match
            # we need to create a new one.
            history_crash = {
                "type"            : "history_crash",
                "product"         : product,
                "branch"          : branch,
                "buildtype"       : buildtype,
                "os_name"         : os_name,
                "os_version"      : os_version,
                "cpu_name"        : cpu_name,
                "firstdatetime"   : timestamp,
                "lastdatetime"    : timestamp,
                "crash"           : crashmessage,
                "crashsignature"  : crashsignature,
                "updatetime"      : timestamp,
                "location_id_list" : [],
                "bug_list"        : None,
                "suppress"        : False
                }
            history_stale = True
            bug_age       = None

            # since the bug list does not depend on the full key
            # try to get a matching crash using just the crashmessage
            # and crashsignature.

            history_crashes = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                           startkey=["history_crash", crashmessage, crashsignature],
                                           endkey=["history_crash", crashmessage, crashsignature + "\u9999"],
                                           include_docs=True)

            if len(history_crashes) > 0:
                for cache in history_crashes:
                    if cache["bug_list"]:
                        break
                if cache["bug_list"]:
                    history_crash["bug_list"]   = cache["bug_list"]
                    history_crash["updatetime"] = cache["updatetime"]
                    bug_age  = 7
                    bug_list = cache["bug_list"]

            try:
                self.testdb.createDocument(history_crash)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        if not bug_list:
            bug_age = None # need to do a full bugzilla search the first time.
            bug_list = {'open' : [], 'closed' : []}

        crashurl_list = self.clean_url_list(crashurl_list)
        crashurl_set = sets.Set(crashurl_list)
        location_id_set  = sets.Set(history_crash["location_id_list"])

        if not crashurl_set.issubset(location_id_set):
            # crashurl_list contains new urls
            history_stale = True

        if history_stale:

            # We do not have a bug_list yet, or the crash was last updated over a day ago.
            # Look up any bugs that match this crash

            if len(crashurl_list) > 0:
                crashurls = ' '.join(crashurl_list)
                self.debugMessage('update_bug_list_crashreports: begin searchBugzillaUrls: %s %s' % (crashurls, bug_age))
                resp, content = sisyphus.bugzilla.searchBugzillaUrls(crashurls, 'contains_any', None, bug_age)
                self.debugMessage('update_bug_list_crashreports: end   searchBugzillaUrls: %s %s' % (crashurls, bug_age))
                if 'bugs' in content:
                    bug_list = self.extractBugzillaBugList(bug_list, content)

            if crashsignature and crashsignature != "0x0":
                self.debugMessage('update_bug_list_crashreports: begin searchBugzillaText: %s %s' % (crashsignature, bug_age))
                resp, content = sisyphus.bugzilla.searchBugzillaText(crashsignature, 'contains_all', None, bug_age)
                self.debugMessage('update_bug_list_crashreports: end   searchBugzillaText: %s %s' % (crashsignature, bug_age))
                if 'bugs' not in content:
                    self.debugMessage('update_bug_list_crashreports: begin searchBugzillaTextAttachments: %s %s' % (crashsignature, bug_age))
                    resp, content = sisyphus.bugzilla.searchBugzillaTextAttachments(crashsignature, 'contains_all', 'crash', bug_age)
                    self.debugMessage('update_bug_list_crashreports: end   searchBugzillaTextAttachments: %s %s' % (crashsignature, bug_age))
                if 'bugs' in content:
                    bug_list = self.extractBugzillaBugList(bug_list, content)

        # Check if the firstdatetime-lastdatetime range should be updated
        # and force an update if necessary.
        if not history_crash["firstdatetime"] or timestamp < history_crash["firstdatetime"]:
            history_crash["firstdatetime"] = timestamp
            history_stale = True
        if not history_crash["lastdatetime"] or timestamp > history_crash["lastdatetime"]:
            history_crash["lastdatetime"] = timestamp
            history_stale = True

        if history_stale:
            history_crash["location_id_list"].extend(crashurl_list)
            # uniqify the location id list.
            history_crash["location_id_list"] = list(sets.Set(history_crash["location_id_list"]))
            history_crash["location_id_list"].sort()
            history_crash["bug_list"]     = bug_list
            history_crash["updatetime"]   = sisyphus.utils.getTimestamp()
            try:
                self.testdb.updateDocument(history_crash, True)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        self.debugMessage('update_bug_list_crashreports: end %s' % bug_list)

    def process_crashreport(self, result_id, product, branch, buildtype, timestamp, crash_report, location_id, test, extra_test_args, dumpextra):

        crash_data = self.parse_crashreport(crash_report)

        os_name              = self.document["os_name"]
        os_version           = self.document["os_version"]
        cpu_name             = self.document["cpu_name"]
        count                = 0
        lastkey              = None
        result_crash_doc     = None


        crashmessage   = crash_data["message"]
        crashsignature = crash_data["signature"]
        currkey = crashmessage + ":" + crashsignature

        self.update_bug_list_crashreports(product, branch, buildtype,
                                          os_name, os_version, cpu_name,
                                          timestamp, crashmessage, crashsignature, [location_id])

        result_crash_doc = {
            "type"            : "result_crash",
            "result_id"       : result_id,
            "product"         : product,
            "branch"          : branch,
            "buildtype"       : buildtype,
            "test"            : test,
            "extra_test_args" : extra_test_args,
            "os_name"         : os_name,
            "os_version"      : os_version,
            "cpu_name"        : cpu_name,
            "worker_id"       : self.document["_id"],
            "datetime"        : timestamp,
            "crash"           : crashmessage,
            "crashsignature"  : crashsignature,
            "location_id"     : location_id,
            "updatetime"      : timestamp,
            "bug"             : "",
            "comment"         : "",
            "extra"           : {}
            }
        for extraproperty in dumpextra:
            if extraproperty != 'ServerURL':
                result_crash_doc["extra"][extraproperty] = dumpextra[extraproperty]
        self.testdb.createDocument(result_crash_doc)

        result_crash_doc = self.testdb.saveAttachment(result_crash_doc, 'crashreport', crash_report, 'text/plain', True, True)


    def updateWorker(self, worker_doc):
        owned = (worker_doc["_id"] == self.document["_id"])

        if owned:
            self.amIOk()

        self.testdb.updateDocument(worker_doc, owned)

    def amIOk(self):
        """
        check our worker document against the database's version
        to make sure we are in sync, and to see if we have been 
        zombied or disabled.
        """

        if not self.document:
            # don't check out state if we haven't been initialized.
            return

        consistent         = True
        worker_id          = self.document["_id"]
        worker_state       = self.document["state"]

        try:
            curr_worker_doc = self.testdb.getDocument(worker_id)

            if not curr_worker_doc:
                # someone deleted our worker document in the database!
                self.testdb.logMessage("amIOk: worker %s was deleted by someone else." % worker_id)
                del self.document['_rev']
                self.testdb.createDocument(self.document)

            if self.document["_rev"] == curr_worker_doc["_rev"]:
                # our revisions match, so the database and the local
                # copy of our worker are in sync.
                pass
            else:
                # our revisions differ, so someone else has updated
                # our worker document in the database.
                self.document["_rev"] = curr_worker_doc["_rev"]
                curr_worker_state       = curr_worker_doc["state"]

                if worker_state != "disabled" and curr_worker_state == "disabled":
                    self.document["state"] = "disabled"
                    consistent               = False

                    self.testdb.logMessage("amIOk: worker %s was disabled." % worker_id)

                elif worker_state != "zombie" and curr_worker_state == "zombie":
                    # we were zombied but are not dead!
                    self.document["state"] = "undead"
                    consistent               = False

                    self.testdb.logMessage("amIOk: worker %s was zombied but is not dead." % worker_id)

        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.testdb.logMessage('amIOk: worker: %s, exception: %s' % (worker_id, errorMessage))
            raise

        if not consistent:
            raise Exception('WorkerInconsistent')


    def getAllWorkers(self, key=None):

        self.debugMessage('getAllWorkers: type: %s' % (self.worker_type))

        for attempt in self.testdb.max_db_attempts:
            try:
                startkey = ['worker_%s' % self.worker_type]
                endkey   = ['worker_%s\u9999' % self.worker_type]
                worker_rows = self.testdb.db.views.default.workers(startkey=startkey, endkey=endkey)
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
                self.testdb.logMessage('getAllWorkers: attempt: %d, key: %s, exception: %s' % (attempt, key, errorMessage))
                self.amIOk()

            if attempt == self.testdb.max_db_attempts[-1]:
                raise Exception("getAllWorkers: aborting after %d attempts" % (self.testdb.max_db_attempts[-1] + 1))
            time.sleep(60)

        if attempt > 0:
            self.testdb.logMessage('getAllWorkers: attempt: %d, success' % (attempt))

        self.debugMessage('getAllWorkers: found %d' % (len(worker_rows)))

        return worker_rows

    def killZombies(self):
        """ zombify any *other* worker who has not updated status in zombie_time hours"""

        self.debugMessage('killZombies(worker.py)')

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
                self.testdb.logMessage("killZombies: worker %s zombifying %s (%s)" % (this_worker_id, worker_row_id, worker_row['datetime']))
                worker_row["state"] = "zombie"
                self.updateWorker(worker_row)

    def BuildDocument(self, product, branch, buildtype, os_name, cpu_name):

        build_id = "%s_%s_%s_%s_%s" % (product, branch, buildtype,
                                       self.document["os_name"].replace(' ', '_'), self.document["cpu_name"])
        build_doc = self.testdb.getDocument(build_id)

        if build_doc is None:
            build_doc = {
                "_id"       : build_id,
                "type"      : "build",
                "product"   : product,
                "branch"    : branch,
                "buildtype" : buildtype,
                "os_name"   : os_name,
                "cpu_name"  : cpu_name,
                "builddate" : None,
                "changeset" : None,
                "worker_id" : self.document["_id"],
                "buildavailable"     : False,
                "state"     : "initializing",
                "datetime"  : sisyphus.utils.getTimestamp()
                }
            try:
                self.testdb.createDocument(build_doc)
            except:
                # assume someone else got it first and try the next branch.
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                if exceptionType == KeyboardInterrupt or exceptionType == SystemExit:
                    raise

                if not re.search('DocumentConflict', str(exceptionValue)):
                    raise
                # Someone beat us to creating the new document. Just return their copy.
                build_doc = self.testdb.getDocument(build_id)

        return build_doc

    def DownloadAndInstallBuild(self, build_doc):
        product   = build_doc["product"]
        branch    = build_doc["branch"]
        buildtype = build_doc["buildtype"]
        os_name   = build_doc["os_name"]
        cpu_name  = build_doc["cpu_name"]

        if not build_doc["buildavailable"]:
            self.logMessage('DownloadAndInstallBuild: build not available %s %s %s' %
                            (product, branch, buildtype))
            return False

        self.document["state"]    = "begin installing %s %s %s" % (product, branch, buildtype)
        self.testdb.logMessage(self.document["state"])

        build_data = self.document[branch]

        build_data["builddate"]       = None
        build_data["buildsuccess"]    = None
        build_data["changeset"]       = None
        build_data["executablepath"]  = None

        self.updateWorker(self.document)

        # clobber old build to make sure we don't mix builds.
        # note clobber essentially rm's the objdir. Pass
        # update_build False to prevent the worker from trying
        # to upload the clobber log to the build document.
        build_doc = self.clobberProduct(build_doc, False)

        productfilename = product + '-' + branch
        symbolsfilename = productfilename + '.crashreporter-symbols.zip'

        # XXX: Do we need to generalize this?
        objdir = '/work/mozilla/builds/%s/mozilla/%s-%s' % (branch, product, buildtype)

        if os_name == 'Windows NT':
            productfilename += '.zip'
            objsubdir = '/dist/bin'
        elif os_name == 'Mac OS X':
            productfilename += '.dmg'
            objsubdir = '/dist'
        elif os_name == 'Linux':
            productfilename += '.tar.bz2'
            objsubdir = '/dist/bin'
        else:
            raise Exception('DownloadAndInstallBuild: unsupported operating system: %s' % os_name)

        build_doc_uri = self.testdb.dburi + '/' + build_doc['_id']
        producturi = build_doc_uri + '/' + productfilename
        symbolsuri = build_doc_uri + '/' + symbolsfilename

        if not sisyphus.utils.downloadFile(producturi, '/tmp/' + productfilename):
            self.logMessage('DownloadAndInstallBuild: failed to download %s %s %s failed' %
                            (product, branch, buildtype))
            return False

        # install-build.sh -p product -b branch -x objdir/dist/bin -f /tmp/productfilename
        cmd = [sisyphus_dir + "/bin/install-build.sh", "-p", product, "-b", branch,
               "-x", objdir + objsubdir, "-f", "/tmp/" + productfilename]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]

        if proc.returncode != 0:
            self.logMessage('DownloadAndInstallBuild: install-build.sh %s %s %s failed: %s' %
                            (product, branch, buildtype, stdout))
            return False

        if sisyphus.utils.downloadFile(symbolsuri, '/tmp/' + symbolsfilename):
            # use command line since ZipFile.extractall isn't available until Python 2.6
            # unzip -d /objdir/dist/crashreporter-symbols /tmp/symbolsfilename
            os.mkdir(objdir + '/dist/crashreporter-symbols')
            cmd = ["unzip", "-d", objdir + "/dist/crashreporter-symbols", "/tmp/" + symbolsfilename]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout = proc.communicate()[0]

            if proc.returncode != 0:
                self.logMessage('DownloadAndInstallBuild: unzip crashreporter-symbols.zip %s %s %s failed: %s' %
                                (product, branch, buildtype, stdout))
                return False

        build_data["builddate"]       = build_doc["builddate"]
        build_data["buildsuccess"]    = True
        build_data["changeset"]       = build_doc["changeset"]
        build_data["executablepath"]  = objdir + '/dist/'

        self.document["state"]    = "success installing %s %s %s" % (product, branch, buildtype)
        self.testdb.logMessage(self.document["state"])
        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        return True

    def NewBuildNeeded(self, build_doc, build_checkup_interval):
        """
        Checks the current state of the build information to determine if a new build
        needs to be created.
        """
        build_needed = False

        if sisyphus.utils.convertTimestamp(build_doc["datetime"]).day != datetime.date.today().day:
            # the build document is over a day old. regardless of its state, it should be rebuilt.
            build_needed = True
        elif build_doc["state"] == "complete":
              if sisyphus.utils.convertTimestamp(build_doc["builddate"]).day != datetime.date.today().day:
                  # the build is over a day old.
                  build_needed = True
        elif build_doc["state"] == "building":
            # someone else is building it.
            if datetime.datetime.now() - sisyphus.utils.convertTimestamp(build_doc["datetime"]) > build_checkup_interval:
                # the build has been "in process" for too long. Consider it dead.
                build_needed = True
        elif build_doc["state"] == "error":
            build_needed = True
        elif build_doc["state"] == "initializing":
            build_needed = True
        else:
            self.logMessage("doWork: unknown build_doc state: %s" % build_doc["state"])

        return build_needed

    def buildProduct(self, build_doc):
        buildsteps      = "checkout build"
        buildchangeset  = None
        buildsuccess    = True
        checkoutlogpath = ''
        buildlogpath    = ''
        builddate       = sisyphus.utils.getTimestamp()
        executablepath  = ''

        product = build_doc["product"]
        branch  = build_doc["branch"]
        buildtype = build_doc["buildtype"]

        build_data = self.document[branch]

        build_data["builddate"]       = None
        build_data["buildsuccess"]    = None
        build_data["changeset"]       = None
        build_data["executablepath"]  = None
        build_data["packagesuccess"]  = None
        build_data["clobbersuccess"]  = None

        self.document["state"]    = "begin building %s %s %s" % (product, branch, buildtype)
        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        self.testdb.logMessage(self.document["state"])

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
            logpathmatch = re.search('log: (.*\.log)', logline)
            if logpathmatch:
                logpath = logpathmatch.group(1)
                checkoutlogmatch = re.search('checkout.log', logpath)
                if checkoutlogmatch:
                    checkoutlogpath = logpath
                    logfile = open(logpath, 'rb')
                    for line in logfile:
                        matchchangeset = re.search('build changeset:.* id (.*)', line)
                        if matchchangeset:
                            buildchangeset = matchchangeset.group(1)
                        if buildchangeset:
                            break
                    logfile.close()
                buildlogmatch = re.search('build.log', logpath)
                if buildlogmatch:
                    buildlogpath = logpath
                    logfile = open(logpath, 'rb')
                    for line in logfile:
                        matchexecutablepath = re.match('environment: executablepath=(.*)', line)
                        if matchexecutablepath:
                            executablepath = matchexecutablepath.group(1)
                        if executablepath:
                            break
                    logfile.close()

        if buildsuccess:
            self.document["state"] = "success building %s %s %s changeset %s" % (product, branch, buildtype, buildchangeset)
        else:
            self.document["state"] = "failure building %s %s %s changeset %s" % (product, branch, buildtype, buildchangeset)

        self.testdb.logMessage(self.document["state"])

        build_data["builddate"]       = builddate
        build_data["buildsuccess"]    = buildsuccess
        build_data["changeset"]       = buildchangeset
        build_data["executablepath"]  = executablepath

        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        if checkoutlogpath:
            build_doc = self.testdb.saveFileAttachment(build_doc, "checkout.log", checkoutlogpath, "text/plain")
            os.unlink(checkoutlogpath)

        if buildlogpath:
            build_doc = self.testdb.saveFileAttachment(build_doc, "build.log", buildlogpath, "text/plain")
            os.unlink(buildlogpath)

        return build_doc

    def clobberProduct(self, build_doc, update_build =True):
        """
        Call Sisyphus to clobber the build. If the worker is
        installing the build rather than building it, pass
        update_build False to prevent the worker from attempting to
        upload the clobber log to the the build_doc.
        """
        buildsteps  = "clobber"
        clobbersuccess = True
        clobberlogpath = ''

        product = build_doc["product"]
        branch  = build_doc["branch"]
        buildtype = build_doc["buildtype"]

        self.document["state"]    = "begin clobbering %s %s %s" % (product, branch, buildtype)

        self.testdb.logMessage(self.document["state"])

        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        proc = subprocess.Popen(
            [
                "rm",
                "-fR",
                "/work/mozilla/builds/%s/mozilla/%s-%s" % (branch, product, buildtype)
                ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        stdout = proc.communicate()[0]

        if proc.returncode != 0:
            clobbersuccess = False

        if clobbersuccess:
            self.document["state"] = 'success clobbering %s %s %s' % (product, branch, buildtype)
            try:
                del self.document[branch]["clobberlog"]
            except:
                pass
        else:
            self.document["state"] = 'failure clobbering %s %s %s' % (product, branch, buildtype)
            self.document[branch]["clobberlog"] = stdout

        self.testdb.logMessage(self.document["state"])

        self.document["datetime"]               = sisyphus.utils.getTimestamp()
        self.document[branch]["clobbersuccess"] = clobbersuccess
        self.updateWorker(self.document)

        if clobberlogpath and update_build:
            build_doc = self.testdb.saveFileAttachment(build_doc, "clobber.log", clobberlogpath, "text/plain")
            os.unlink(clobberlogpath)

        return build_doc

    def packageProduct(self, build_doc):
        packagesuccess = True

        product = build_doc["product"]
        branch  = build_doc["branch"]
        buildtype = build_doc["buildtype"]

        self.document["state"] = 'begin packaging %s %s %s' % (product, branch, buildtype)

        self.testdb.logMessage(self.document["state"])

        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        # remove any stale package files
        executablepath = self.document[branch]["executablepath"]
        productfiles = glob.glob(os.path.join(executablepath, product + '-*'))
        for productfile in productfiles:
            os.unlink(productfile)

        # SYM_STORE_SOURCE_DIRS= required due to bug 534992
        proc = subprocess.Popen(
            [
                sisyphus_dir + "/bin/set-build-env.sh",
                "-p", product,
                "-b", branch,
                "-T", buildtype,
                "-c", "make -C firefox-%s package package-tests buildsymbols SYM_STORE_SOURCE_DIRS=" % (buildtype)
                ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        packagelog = proc.communicate()[0]

        if proc.returncode == 0:
            # too verbose and not useful if succeeded.
            packagelog = 'success'
        else:
            packagesuccess = False

        if packagesuccess:
            self.document["state"] = 'success packaging %s %s %s' % (product, branch, buildtype)
        else:
            self.document["state"] = 'failure packaging %s %s %s' % (product, branch, buildtype)

        self.testdb.logMessage(self.document["state"])

        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.document[branch]["packagesuccess"] = packagesuccess
        self.updateWorker(self.document)

        if not self.document[branch]["packagesuccess"]:
            build_doc = self.testdb.saveAttachment(build_doc, "package.log", packagelog, "text/plain")

        return build_doc

    def uploadProduct(self, build_doc):

        product   = build_doc["product"]
        branch    = build_doc["branch"]
        buildtype = build_doc["buildtype"]

        uploadsuccess = True

        self.document["state"] = 'begin uploading %s %s %s' % (product, branch, buildtype)

        self.testdb.logMessage(self.document["state"])

        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.document[branch]["uploadsuccess"] = uploadsuccess
        self.updateWorker(self.document)

        executablepath = self.document[branch]["executablepath"]

        if not os.path.exists(executablepath):
            uploadsuccess = False
            self.testdb.logMessage('executablepath %s does not exist' % executablepath)

        if not os.path.isdir(executablepath):
            uploadsuccess = False
            self.testdb.logMessage('executablepath %s is not a directory' % executablepath)

        productfiles = glob.glob(os.path.join(executablepath, product + '-*'))
        if len(productfiles) == 0:
            uploadsuccess = False
            self.testdb.logMessage('executablepath %s does not contain product files %s-*' % (executablepath, product))

        build_doc["buildavailable"] = False

        build_doc["builddate"] = self.document[branch]["builddate"]
        build_doc["changeset"] = self.document[branch]["changeset"]
        build_doc["worker_id"] = self.document["_id"]

        for productfile in productfiles:
            productfilename = os.path.basename(productfile)
            content_type    = 'application/octet-stream'

            if re.search('\.txt$', productfilename):
                content_type = 'text/plain'
                productfilename = "%s-%s.txt" % (product, branch)
            elif re.search('\.langpack\.xpi$', productfilename):
                content_type = 'application/x-xpinstall'
                productfilename = "%s-%s.langpack.xpi" % (product, branch)
            elif re.search('\.crashreporter-symbols\.zip$', productfilename):
                content_type = 'application/x-zip-compressed'
                productfilename = "%s-%s.crashreporter-symbols.zip" % (product, branch)
            elif re.search('\.tests.zip$', productfilename):
                content_type = 'application/x-zip-compressed'
                productfilename = "%s-%s.tests.zip" % (product, branch)
            elif re.search('\.tests.tar.bz2$', productfilename):
                content_type = 'application/octet-stream'
                productfilename = "%s-%s.tests.tar.bz2" % (product, branch)
            elif re.search('\.zip$', productfilename):
                content_type = 'application/x-zip-compressed'
                productfilename = "%s-%s.zip" % (product, branch)
            elif re.search('\.tar.bz2$', productfilename):
                content_type = 'application/octet-stream'
                productfilename = "%s-%s.tar.bz2" % (product, branch)
            elif re.search('\.dmg$', productfilename):
                content_type = 'application/octet-stream'
                productfilename = "%s-%s.dmg" % (product, branch)

            try:
                build_doc = self.testdb.saveFileAttachment(build_doc, productfilename, productfile, content_type)
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                self.testdb.logMessage('uploadProduct: %s' % errorMessage)
                uploadsuccess = False

        if uploadsuccess:
            build_doc["buildavailable"] = True
            build_doc["state"] = "complete"
            self.document["state"] = 'success uploading %s %s %s' % (product, branch, buildtype)
        else:
            self.document["state"] = 'failure uploading %s %s %s' % (product, branch, buildtype)

        self.testdb.logMessage(self.document["state"])

        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.document[branch]["uploadsuccess"] = uploadsuccess
        self.updateWorker(self.document)

        return build_doc

    def publishNewBuild(self, build_doc):

        product   = build_doc["product"]
        branch    = build_doc["branch"]
        buildtype = build_doc["buildtype"]

        try:
            build_doc["datetime"] = sisyphus.utils.getTimestamp()
            build_doc["state"] = "building"
            self.testdb.updateDocument(build_doc)
        except:
            # If a DocumentConflict occurred, someone else has starting working on the build first.
            # Mark this build locally as not a success, but don't mark it as an error in the builds db.
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt or exceptionType == SystemExit:
                raise
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.logMessage('doWork: updating build document %s %s %s: %s' %
                                   (product, branch, buildtype, errorMessage))
            if not re.search('DocumentConflict', str(exceptionValue)):
                raise
            build_doc["state"] = "error"
            self.document[branch]["buildsuccess"] = False
            return build_doc

        # kill any test processes still running.
        self.killTest()
        try:
            build_doc = self.buildProduct(build_doc)
            if not self.document[branch]["buildsuccess"]:
                # don't wait if a build failure occurs
                build_doc["state"] = "error"
                build_doc = self.clobberProduct(build_doc)
            else:
                build_doc = self.packageProduct(build_doc)
                if self.document[branch]["packagesuccess"]:
                    build_doc = self.uploadProduct(build_doc)

            build_doc["datetime"] = sisyphus.utils.getTimestamp()
            self.testdb.updateDocument(build_doc)
        except:
            build_doc["datetime"] = sisyphus.utils.getTimestamp()
            build_doc["state"] = "error"
            self.testdb.updateDocument(build_doc)

            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType == KeyboardInterrupt or exceptionType == SystemExit:
                raise

            # assume someone else got it first and try the next branch.
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.logMessage('doWork: finishing build document %s %s %s: %s' %
                                   (product, branch, buildtype, errorMessage))

        return build_doc

    def update_bug_histories(self):

        if not self.lock_history_update():
            return

        checkup_interval = datetime.timedelta(minutes=5)
        last_checkup_time = datetime.datetime.now() - 2*checkup_interval

        try:
            crash_rows = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                      startkey=["history_crash"],
                                      endkey=["history_crash\u9999"],
                                      include_docs=True)

            for crash_doc in crash_rows:
                if datetime.datetime.now() - last_checkup_time > checkup_interval:
                    self.document['datetime'] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    last_checkup_time = datetime.datetime.now()

                self.update_bug_list_crashreports(crash_doc["product"], crash_doc["branch"], crash_doc["buildtype"],
                                                  crash_doc["os_name"], crash_doc["os_version"], crash_doc["cpu_name"], None,
                                                  crash_doc["crash"], crash_doc["crashsignature"], crash_doc["location_id_list"])
        except KeyboardInterrupt:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            # XXX: kludge to not have to implement this in each descendent class
            if str(exceptionValue) != 'No view named crashes. ':
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                self.logMessage("update_bug_histories: error updating crashes: %s exception: %s" %
                                (exceptionValue, errorMessage))

        try:
            valgrind_rows = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                         startkey=["history_valgrind"],
                                         endkey=["history_valgrind\u9999"],
                                         include_docs=True)

            for valgrind_doc in valgrind_rows:
                if datetime.datetime.now() - last_checkup_time > checkup_interval:
                    self.document['datetime'] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    last_checkup_time = datetime.datetime.now()

                self.update_bug_list_valgrinds(valgrind_doc["product"], valgrind_doc["branch"], valgrind_doc["buildtype"],
                                               valgrind_doc["os_name"], valgrind_doc["os_version"], valgrind_doc["cpu_name"], None,
                                               valgrind_doc["valgrind"], valgrind_doc["valgrindsignature"], valgrind_doc["location_id_list"])
        except KeyboardInterrupt:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.logMessage("update_bug_histories: error updating valgrinds: %s exception: %s" %
                            (exceptionValue, errorMessage))

        try:
            assertion_rows = self.getRows(self.testdb.db.views.bughunter.results_by_type,
                                          startkey=["history_assertion"],
                                          endkey=["history_assertion\u9999"],
                                          include_docs=True)

            for assertion_doc in assertion_rows:
                if datetime.datetime.now() - last_checkup_time > checkup_interval:
                    self.document['datetime'] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    last_checkup_time = datetime.datetime.now()

                self.update_bug_list_assertions(assertion_doc["product"], assertion_doc["branch"], assertion_doc["buildtype"],
                                                assertion_doc["os_name"], assertion_doc["os_version"], assertion_doc["cpu_name"], None,
                                                assertion_doc["assertion"], assertion_doc["assertionfile"], assertion_doc["location_id_list"])
        except KeyboardInterrupt:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.logMessage("update_bug_histories: error updating assertions. %s exception: %s" %
                            (exceptionValue, errorMessage))

        self.unlock_history_update()

    def lock_history_update(self):

        timestamp = sisyphus.utils.getTimestamp()
        now       = sisyphus.utils.convertTimestamp(timestamp)
        yesterday = now - datetime.timedelta(days=1)

        try:
            update_doc = self.testdb.getDocument('update')

            if not update_doc:
                # first time bug history updated.
                update_doc = { "_id" : "update", self.testdb.dburi : { "datetime" : timestamp, "worker_id" : self.document["_id"] }}
                self.testdb.createDocument(update_doc)

            elif self.testdb.dburi not in update_doc:
                # first time bug history updated for this db.
                update_doc[self.testdb.dburi] = { "datetime" : timestamp, "worker_id" : self.document["_id"]}

            elif sisyphus.utils.convertTimestamp(update_doc[self.testdb.dburi]["datetime"]) > yesterday:
                # either someone else is updating history or it is current and doesn't need updating
                return False

            # any worker_id information is stale and can be ignored.
            update_doc[self.testdb.dburi]["worker_id"] = self.document["_id"]
            update_doc[self.testdb.dburi]["datetime"]  = timestamp
            self.testdb.updateDocument(update_doc)
            update_doc = self.testdb.getDocument("update")
            if update_doc[self.testdb.dburi]["worker_id"] != self.document["_id"]:
                # race condition. someone beat us to it.
                return False

        except:
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.testdb.logMessage('update_bug_history: worker: %s, exception: %s' % (worker_id, errorMessage))
            raise

        self.testdb.logMessage("updating bug histories")

        self.document["state"]    = "begin updating bug histories"
        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        return True

    def unlock_history_update(self):

        update_doc = self.testdb.getDocument('update')

        if not update_doc or self.testdb.dburi not in update_doc or update_doc[self.testdb.dburi]["worker_id"] != self.document["_id"]:
            raise Exception('HistoryUpdateLockConflict')

        self.testdb.logMessage("finished updating bug histories")

        self.document["state"]    = "finished updating bug histories"
        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        update_doc[self.testdb.dburi]["worker_id"] = None
        update_doc[self.testdb.dburi]["datetime"]  = sisyphus.utils.getTimestamp()
        self.testdb.updateDocument(update_doc, True)

    def killTest(self):
        # XXX: os.kill fails to kill the entire test process and children when
        # a test times out. This is most noticible on Windows but can occur on
        # Linux as well. To kill the test reliably, use the external kill program
        # to kill all processes running from the /work/mozilla/builds/[^/]+/mozilla/ directory
        # build tree.
        # Windows will have a leading space, however Linux, Mac OS X will not.

        #build_dir     = os.environ["BUILD_DIR"]
        build_dir     = '/work/mozilla/builds'
        build_pattern = r' *([0-9]+).*%s[/\\][^/\\]+[/\\]mozilla[/\\]' % build_dir.replace('/', '[/\\]')

        if self.document["os_name"] != "Windows NT":
            ps_proc = subprocess.Popen(["ps", "-ax"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            kill_args = ["/bin/kill", "-9"]
        else:
            ps_proc = subprocess.Popen(["ps", "-W"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            kill_args = ["/bin/kill", "-f", "-9"]

        kill_pids = []
        for ps_line in ps_proc.stdout:
            ps_match = re.search(build_pattern, ps_line)
            if ps_match:
                kill_pids.append(ps_match.group(1))

        # kill them all.
        if len(kill_pids) > 0:
            kill_args.extend(kill_pids)
            subprocess.call(kill_args)

    def getRows(self, view, startkey = None, endkey = None, include_docs = None):
        """
        return rows from view in self.testdb matching startkey, endkey with
        connection recovery.
        """
        if include_docs is None:
            include_docs = False

        rows = None

        for attempt in self.testdb.max_db_attempts:
            try:
                if startkey and endkey:
                    rows = view(startkey=startkey, endkey=endkey, include_docs=include_docs)
                elif startkey:
                    rows = view(startkey=startkey, include_docs=include_docs)
                else:
                    rows = view(include_docs=include_docs)

                if include_docs:
                    # the view does not define the value as the full document.
                    # retrieve the document from the raw_rows.
                    rows = [row['doc'] for row in rows.raw_rows()]
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
                self.logMessage('getRows: attempt: %d, startkey: %s, endkey: %s, exception: %s' %
                                (attempt, startkey, endkey, errorMessage))
                self.amIOk()

            if attempt == self.testdb.max_db_attempts[-1]:
                raise Exception("getRows: aborting after %d attempts" % (self.testdb.max_db_attempts[-1] + 1))
            time.sleep(60)

        if attempt > 0:
            self.logMessage('getRows: attempt: %d, success' % (attempt))

        return rows

