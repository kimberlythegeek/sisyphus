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

class BuildWorker(sisyphus.worker.Worker):

    def __init__(self, startdir, programPath, couchserveruri, couchdbname, worker_comment, debug):
        sisyphus.worker.Worker.__init__(self, "builder", startdir, programPath, couchserveruri, couchdbname, worker_comment, debug)

    def doWork(self):

        waittime = 0
        buildtype = "debug"
        product = "firefox"

        daily_checkup_interval = datetime.timedelta(days=1)
        daily_last_checkup_time = datetime.datetime.now() - 2*daily_checkup_interval

        build_checkup_interval = datetime.timedelta(hours=3)

        checkup_interval = datetime.timedelta(minutes=5)
        last_checkup_time = datetime.datetime.now() - 2*checkup_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate()
                self.testdb.checkDatabase()
                self.killZombies()
                last_checkup_time = datetime.datetime.now()

            sys.stdout.flush()
            time.sleep(waittime)
            waittime = 3600

            branches_doc = self.testdb.getDocument('branches')

            branches = branches_doc['branches']

            for branch in branches:

                build_needed = False

                build_doc = self.BuildDocument(product, branch, buildtype, self.document["os_name"], self.document["cpu_name"])

                if self.NewBuildNeeded(build_doc, build_checkup_interval):

                    build_doc = self.publishNewBuild(build_doc)
                    if build_doc["state"] == "error":
                        # A build error occurred. Do not wait before attempting new builds
                        waittime = 0

            if datetime.datetime.now() - daily_last_checkup_time > daily_checkup_interval:
                self.update_bug_histories()

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

    this_worker = BuildWorker(startdir, programPath,
                              options.couchserveruri, options.databasename,
                              options.worker_comment, options.debug)

    programModTime = os.stat(programPath)[stat.ST_MTIME]

    this_worker.logMessage('starting worker %s %s %s with program dated %s' %
                          (this_worker.document['os_name'], this_worker.document['os_version'],
                           this_worker.document['cpu_name'],
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
        this_worker.logMessage('Program restarting', True)
        this_worker.reloadProgram()
    else:
        this_worker.logMessage('Program terminating', False)
        this_worker.testdb.deleteDocument(this_worker.document, False)


