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

from sisyphus.webapp.bughunter import models
from sisyphus.automation import utils, program_info
#import sisyphus.automation.builder
import sisyphus.automation.worker

options          = None

class BuildWorker(sisyphus.automation.worker.Worker):

    def __init__(self, options):
        options.build = True
        sisyphus.automation.worker.Worker.__init__(self, "builder", options)

    def doWork(self):

        waittime                = 0
        daily_checkup_interval  = datetime.timedelta(days=1)
        daily_last_checkup_time = datetime.datetime.now() - 2*daily_checkup_interval
        build_checkup_interval  = datetime.timedelta(hours=3)
        checkup_interval        = datetime.timedelta(minutes=5)
        last_checkup_time       = datetime.datetime.now() - 2*checkup_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate()
                self.killZombies()
                last_checkup_time = datetime.datetime.now()

            sys.stdout.flush()
            self.state = 'waiting'
            self.save()
            time.sleep(waittime)

            waittime = 3600

            for self.product in self.builddata:
                for self.branch in self.builddata[self.product]:
                    for self.buildtype in self.builddata[self.product][self.branch]:
                        if self.isNewBuildNeeded(build_checkup_interval):

                            self.publishNewBuild()
                            if self.build_row.state == "error":
                                # A build error occurred. Do not wait before attempting new builds
                                waittime = 0

                        # check for update after each build we don't have to wait
                        # for all of the builds to complete if the program needs
                        # to be restarted.
                        self.checkForUpdate()

program_info.init(globals())

def main():

    global options, this_worker

    this_worker = None

    usage = '''usage: %prog [options]'''

    parser = OptionParser(usage=usage)
    parser.add_option('--nodebug', action='store_false',
                      dest='debug',
                      default=False,
                      help='default - no debug messages')
    parser.add_option('--debug', action='store_true',
                      dest='debug',
                      help='turn on debug messages')
    (options, args) = parser.parse_args()

    exception_counter = 0

    this_worker = BuildWorker(options)

    this_worker.logMessage('starting worker %s %s %s with program dated %s' %
                          (this_worker.os_name, this_worker.os_version, this_worker.cpu_name,
                           time.ctime(program_info.programModTime)))
    while True:
        try:
            this_worker.doWork()
        except KeyboardInterrupt, SystemExit:
            raise
        except:

            exception_counter += 1
            if exception_counter > 100:
                print "Too many errors. Terminating."
                exit(2)

            exceptionType, exceptionValue, errorMessage = utils.formatException()

            if str(exceptionValue) == 'WorkerInconsistent':
                # If we were disabled, sleep for 5 minutes and check our state again.
                # otherwise restart.
                if this_worker.state == "disabled":
                    while True:
                        time.sleep(300)
                        try:
                            curr_worker_row = models.Worker.objects.get(hostname = this_worker.hostname)

                        except models.Worker.DoesNotExist:
                            # we were deleted. just terminate
                            exit(2)

                        if curr_worker_row.state != "disabled":
                            this_worker.state = "waiting"
                            this.worker.save()
                            break

            this_worker.logMessage('main: exception %s: %s' % (str(exceptionValue), errorMessage))

            time.sleep(60)


if __name__ == "__main__":
    try:
        restart = True
        main()
    except KeyboardInterrupt, SystemExit:
        restart = False
    except:
        exceptionType, exceptionValue, errorMessage = utils.formatException()
        if str(exceptionValue) not in "0,NormalExit":
            print ('main: exception %s: %s' % (str(exceptionValue), errorMessage))

    if this_worker is None:
        exit(2)

    if restart:
        this_worker.logMessage('Program restarting')
        this_worker.reloadProgram()

    this_worker.logMessage('Program terminating')
    # No longer delete workers as the sql referential interegrity in the db will delete
    # everything that references the worker as a foreign key.
    this_worker.state = 'dead'
    this_worker.save()


