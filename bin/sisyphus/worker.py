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

sisyphus_dir     = os.environ["TEST_DIR"]
sys.path.append(os.path.join(sisyphus_dir,'bin'))

import sisyphus.utils
import sisyphus.couchdb
import sisyphus.bugzilla

class Worker():
    def __init__(self, startdir, programPath, testdb, historydb, worker_comment, branches, debug = False):
        self.startdir       = startdir
        self.programPath    = programPath
        self.programModTime = os.stat(programPath)[stat.ST_MTIME]
        self.debug          = debug
        self.testdb         = testdb
        self.testdb.debug   = debug
        self.historydb      = historydb
        self.historydb.debug = debug
        self.zombie_time    = 6 # if a worker hasn't updated datetime in zombie_time hours, it will be killed.

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

        if not worker_doc:
            self.document = {"_id"          : host_name,
                               "type"         : "worker",
                               "os_name"      : os_name,
                               "os_version"   : os_version,
                               "cpu_name"     : cpu_name,
                               "comment"      : worker_comment,
                               "datetime"     : sisyphus.utils.getTimestamp(),
                               "state"        : "new"}


            # add build information to the worker document.
            for branch in branches:
                self.document[branch] = {"builddate" : None, "changeset" : None }

            self.testdb.createDocument(self.document)

        else:
            self.document = worker_doc

            self.document["_id"]          = host_name
            self.document["type"]         = "worker"
            self.document["os_name"]      = os_name
            self.document["os_version"]   = os_version
            self.document["cpu_name"]     = cpu_name
            self.document["comment"]      = worker_comment
            self.document["datetime"]     = sisyphus.utils.getTimestamp()
            self.document["state"]        = "recycled"

            # add build information to the worker document if it isn't there already.
            for branch in branches:
                if not branch in self.document:
                    self.document[branch] = {"builddate" : None, "changeset" : None }

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

    def checkForUpdate(self, job_doc):
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

    def update_bug_list_assertions(self, product, branch, buildtype, os_name, os_version, cpu_name, timestamp, assertionmessage, assertionfile):
        """
        check for cached bug data in similar assertions in the
        last day of unittests or the assertion history.
        """

        self.debugMessage('update_bug_list_assertions: start: %s %s' % (assertionmessage, assertionfile))

        bug_list           = None
        now                = datetime.datetime.now()

        history_assertions = self.getRows(self.historydb.db.views.default.assertions,
                                          startkey=[assertionmessage, assertionfile, product, branch, buildtype, os_name, os_version, cpu_name],
                                          endkey=[assertionmessage, assertionfile, product, branch, buildtype, os_name, os_version, cpu_name + "\u9999"],
                                          include_docs=True)

        if len(history_assertions) > 0:

            history_assertion  = history_assertions[0]
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
                        self.historydb.deleteDocument(history_assertions[iassertion])
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
                "type"            : "assertion",
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
                "bug_list"        : None,
                "suppress"        : False
                }
            history_stale  = True
            bug_age        = None

            # since the bug list does not depend on the full key
            # try to get a matching assertion using just the assertionmessage.

            history_assertions = self.getRows(self.historydb.db.views.default.assertions,
                                              startkey=[assertionmessage],
                                              endkey=[assertionmessage + "\u9999"],
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
                self.historydb.createDocument(history_assertion)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        if history_stale and assertionmessage:

            # We do not have a bug_list yet, or the assertion was last updated over a day ago.
            # Look up any bugs that match this assertion

            if not bug_list:
                bug_age = None # need to do a full bugzilla search the first time.
                bug_list = {'open' : [], 'closed' : []}

            self.debugMessage('update_bug_list_assertions: begin searchBugzillaText: %s %s' % (assertionmessage, bug_age))
            resp, content = sisyphus.bugzilla.searchBugzillaText(assertionmessage, 'contains', None, bug_age)
            self.debugMessage('update_bug_list_assertions: end   searchBugzillaText: %s %s' % (assertionmessage, bug_age))

            if 'bugs' in content:
                bug_list = self.extractBugzillaBugList(bug_list, content)

        if history_stale:
            history_assertion["bug_list"]     = bug_list
            history_assertion["lastdatetime"] = timestamp
            history_assertion["updatetime"]   = timestamp
            try:
                self.historydb.updateDocument(history_assertion, True)
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
                                                timestamp, assertionmessage, assertionfile)

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

    def update_bug_list_valgrinds(self, product, branch, buildtype, os_name, os_version, cpu_name, timestamp, valgrindmessage, valgrindsignature):
        """
        check for cached bug data in similar valgrinds in the
        last day of unittests or the valgrind history.
        """

        self.debugMessage('update_bug_list_valgrinds: start: %s %s' % (valgrindmessage, valgrindsignature))

        bug_list           = None
        now                = datetime.datetime.now()

        history_valgrinds = self.getRows(self.historydb.db.views.default.valgrind,
                                         startkey=[valgrindmessage, valgrindsignature, product, branch, buildtype, os_name, os_version, cpu_name],
                                         endkey=[valgrindmessage, valgrindsignature, product, branch, buildtype, os_name, os_version, cpu_name + "\u9999"],
                                         include_docs=True)

        if len(history_valgrinds) > 0:

            history_valgrind   = history_valgrinds[0]
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
                        self.historydb.deleteDocument(history_valgrinds[ivalgrind])
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
                "type"            : "valgrind",
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
                "updatetime"      : timestamp,
                "bug_list"        : None,
                "suppress"        : False
                }
            history_stale = True
            bug_age       = None

            # since the bug list does not depend on the full key
            # try to get a matching valgrind using just the valgrindmessage
            # and valgrindsignature.

            history_valgrinds = self.getRows(self.historydb.db.views.default.valgrind,
                                             startkey=[valgrindmessage, valgrindsignature],
                                             endkey=[valgrindmessage, valgrindsignature + "\u9999"],
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
                self.historydb.createDocument(history_valgrind)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        if history_stale and valgrindsignature:

            # We do not have a bug_list yet, or the valgrind was last updated over a day ago.
            # Look up any bugs that match this valgrind

            if not bug_list:
                bug_age = None # need to do a full bugzilla search the first time.
                bug_list = {'open' : [], 'closed' : []}

            self.debugMessage('update_bug_list_valgrinds: begin searchBugzillaText: %s %s' % (valgrindsignature, bug_age))
            resp, content = sisyphus.bugzilla.searchBugzillaText(valgrindsignature, 'contains_all', None, bug_age)
            self.debugMessage('update_bug_list_valgrinds: end   searchBugzillaText: %s %s' % (valgrindsignature, bug_age))

            if 'bugs' in content:
                bug_list = self.extractBugzillaBugList(bug_list, content)

        if history_stale:
            history_valgrind["bug_list"]     = bug_list
            history_valgrind["lastdatetime"] = timestamp
            history_valgrind["updatetime"]   = timestamp
            try:
                self.historydb.updateDocument(history_valgrind, True)
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
            currkey = valgrindmessage + ":" + valgrindsignature

            if result_valgrind_doc and lastkey and lastkey != currkey:
                result_valgrind_doc["count"] = count
                self.testdb.updateDocument(result_valgrind_doc, True)
                result_valgrind_doc = None
                count = 0

            elif result_valgrind_doc is None:

                self.update_bug_list_valgrinds(product, branch, buildtype,
                                               os_name, os_version, cpu_name,
                                               timestamp, valgrindmessage, valgrindsignature)

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
        check for cached bug data in similar crashreports in the
        last day of crashreports or the crashreport history.
        """

        self.debugMessage('update_bug_list_crashreports: start: %s %s %s' % (crashmessage, crashsignature, crashurl_list))

        bug_list           = None
        now                = datetime.datetime.now()

        history_crashes = self.getRows(self.historydb.db.views.default.crashes,
                                       startkey=[crashmessage, crashsignature, product, branch, buildtype, os_name, os_version, cpu_name],
                                       endkey=[crashmessage, crashsignature, product, branch, buildtype, os_name, os_version, cpu_name + "\u9999"],
                                       include_docs=True)

        if len(history_crashes) > 0:

            history_crash      = history_crashes[0]
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
                        self.historydb.deleteDocument(history_crashes[icrash])
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
                "type"            : "crash",
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

            history_crashes = self.getRows(self.historydb.db.views.default.crashes,
                                           startkey=[crashmessage, crashsignature],
                                           endkey=[crashmessage, crashsignature + "\u9999"],
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
                self.historydb.createDocument(history_crash)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        if not bug_list:
            bug_age = None # need to do a full bugzilla search the first time.
            bug_list = {'open' : [], 'closed' : []}

        if history_stale:

            # We do not have a bug_list yet, or the crash was last updated over a day ago.
            # Look up any bugs that match this crash

            # remove special 'head' url.
            while len(crashurl_list) > 0:
                try:
                    crashurl_list.remove('head')
                except ValueError:
                    break

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

        if history_stale:
            history_crash["location_id_list"].extend(crashurl_list)
            # uniqify the location id list.
            history_crash["location_id_list"] = list(sets.Set(history_crash["location_id_list"]))
            history_crash["location_id_list"].sort()
            history_crash["bug_list"]     = bug_list
            history_crash["lastdatetime"] = timestamp
            history_crash["updatetime"]   = timestamp
            try:
                self.historydb.updateDocument(history_crash, True)
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('updateDocumentConflict', str(exceptionValue)):
                    raise

        self.debugMessage('update_bug_list_crashreports: end %s' % bug_list)

    def process_crashreport(self, result_id, product, branch, buildtype, timestamp, crash_data, location_id, test, extra_test_args):

        os_name              = self.document["os_name"]
        os_version           = self.document["os_version"]
        cpu_name             = self.document["cpu_name"]
        count                = 0
        lastkey              = None
        result_crash_doc     = None


        crashmessage      = crash_data["message"]
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
            "comment"         : ""
            }
        self.testdb.createDocument(result_crash_doc)

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
        for attempt in self.testdb.max_db_attempts:
            try:
                worker_rows = self.testdb.db.views.default.workers()
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

        return worker_rows

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
                self.testdb.logMessage("killZombies: worker %s zombifying %s (%s)" % (this_worker_id, worker_row_id, worker_row['datetime']))
                worker_row["state"] = "zombie"
                self.updateWorker(worker_row)

    def buildProduct(self, product, branch, buildtype):
        buildsteps  = "checkout build"
        buildchangeset = None
        buildsuccess = True

        self.document["state"]    = "building %s %s %s" % (product, branch, buildtype)
        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        self.testdb.logMessage('begin building %s %s %s' % (product, branch, buildtype))

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
            self.testdb.logMessage('success building %s %s %s changeset %s' % (product, branch, buildtype, buildchangeset))
            self.document["state"]    = "success building %s %s %s" % (product, branch, buildtype)
            self.document["datetime"] = sisyphus.utils.getTimestamp()
            self.document[branch]["builddate"] = sisyphus.utils.getTimestamp()
            self.document[branch]["changeset"] = buildchangeset
            self.updateWorker(self.document)
        else:
            self.testdb.logMessage('failure building %s %s %s changeset %s' % (product, branch, buildtype, buildchangeset))
            self.document["state"]        = "failure building %s %s %s, clobbering..." % (product, branch, buildtype)
            self.document["datetime"]     = sisyphus.utils.getTimestamp()
            self.document[branch]["builddate"] = None
            self.document[branch]["changeset"] = None
            self.updateWorker(self.document)

        return {"changeset" : buildchangeset, "success" : buildsuccess}

    def clobberProduct(self, product, branch, buildtype):
        buildsteps  = "clobber"
        buildchangeset = None
        buildsuccess = True

        self.testdb.logMessage('begin clobbering %s %s %s' % (product, branch, buildtype))

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
            self.testdb.logMessage('success clobbering %s %s %s' % (product, branch, buildtype))
        else:
            self.testdb.logMessage('failure clobbering %s %s %s' % (product, branch, buildtype))

        return buildsuccess

    def update_bug_histories(self):

        if not self.lock_history_update():
            return

        timestamp   = sisyphus.utils.getTimestamp()
        now         = sisyphus.utils.convertTimestamp(timestamp)
        yesterday   = now - datetime.timedelta(days=1)

        checkup_interval = datetime.timedelta(minutes=5)
        last_checkup_time = datetime.datetime.now() - 2*checkup_interval

        try:
            crash_rows = self.getRows(self.historydb.db.views.default.crashes, include_docs=True)

            for crash_doc in crash_rows:
                if datetime.datetime.now() - last_checkup_time > checkup_interval:
                    self.document['datetime'] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    last_checkup_time = datetime.datetime.now()

                self.update_bug_list_crashreports(crash_doc["product"], crash_doc["branch"], crash_doc["buildtype"],
                                                  crash_doc["os_name"], crash_doc["os_version"], crash_doc["cpu_name"], timestamp,
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
            valgrind_rows = self.getRows(self.historydb.db.views.default.valgrind, include_docs=True)

            for valgrind_doc in valgrind_rows:
                if datetime.datetime.now() - last_checkup_time > checkup_interval:
                    self.document['datetime'] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    last_checkup_time = datetime.datetime.now()

                self.update_bug_list_valgrinds(valgrind_doc["product"], valgrind_doc["branch"], valgrind_doc["buildtype"],
                                               valgrind_doc["os_name"], valgrind_doc["os_version"], valgrind_doc["cpu_name"], timestamp,
                                               valgrind_doc["valgrind"], valgrind_doc["valgrindsignature"])
        except KeyboardInterrupt:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.logMessage("update_bug_histories: error updating valgrinds: %s exception: %s" %
                            (exceptionValue, errorMessage))

        try:
            assertion_rows = self.getRows(self.historydb.db.views.default.assertions, include_docs=True)

            for assertion_doc in assertion_rows:
                if datetime.datetime.now() - last_checkup_time > checkup_interval:
                    self.document['datetime'] = sisyphus.utils.getTimestamp()
                    self.updateWorker(self.document)
                    last_checkup_time = datetime.datetime.now()

                self.update_bug_list_assertions(assertion_doc["product"], assertion_doc["branch"], assertion_doc["buildtype"],
                                                assertion_doc["os_name"], assertion_doc["os_version"], assertion_doc["cpu_name"], timestamp,
                                                assertion_doc["assertion"], assertion_doc["assertionfile"])
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

        historydburi = self.historydb.db.__dict__['uri']

        try:
            update_doc = self.historydb.getDocument('update')

            if not update_doc:
                # first time bug history updated.
                update_doc = { "_id" : "update", historydburi : { "datetime" : timestamp, "worker_id" : self.document["_id"] }}
                self.historydb.createDocument(update_doc)

            elif historydburi not in update_doc:
                # first time bug history updated for this db.
                update_doc[historydburi] = { "datetime" : timestamp, "worker_id" : self.document["_id"]}

            elif sisyphus.utils.convertTimestamp(update_doc[historydburi]["datetime"]) > yesterday:
                # either someone else is updating history or it is current and doesn't need updating
                return False

            # any worker_id information is stale and can be ignored.
            update_doc[historydburi]["worker_id"] = self.document["_id"]
            update_doc[historydburi]["datetime"]  = timestamp
            self.historydb.updateDocument(update_doc)
            update_doc = self.historydb.getDocument("update")
            if update_doc[historydburi]["worker_id"] != self.document["_id"]:
                # race condition. someone beat us to it.
                return False

        except:
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
            self.testdb.logMessage('update_bug_history: worker: %s, exception: %s' % (worker_id, errorMessage))
            raise

        self.testdb.logMessage("updating bug histories")

        self.document["state"]    = "beginning updating bug histories"
        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        return True

    def unlock_history_update(self):

        historydburi = self.historydb.db.__dict__['uri']

        update_doc = self.historydb.getDocument('update')

        if not update_doc or historydburi not in update_doc or update_doc[historydburi]["worker_id"] != self.document["_id"]:
            raise Exception('HistoryUpdateLockConflict')

        self.testdb.logMessage("finished updating bug histories")

        self.document["state"]    = "finished updating bug histories"
        self.document["datetime"] = sisyphus.utils.getTimestamp()
        self.updateWorker(self.document)

        update_doc[historydburi]["worker_id"] = None
        update_doc[historydburi]["datetime"]  = sisyphus.utils.getTimestamp()
        self.historydb.updateDocument(update_doc, True)

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

