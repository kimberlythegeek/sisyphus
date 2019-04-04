# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
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

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from bughunter import models
from automation import utils, program_info
import automation.worker

options          = None

class BuildWorker(automation.worker.Worker):

    def __init__(self, options):
        options.build = True
        automation.worker.Worker.__init__(self, "builder", options)

    def doWork(self):

        waittime                = 0
        build_checkup_interval  = datetime.timedelta(hours=3)

        checkup_interval        = datetime.timedelta(minutes=5)
        last_checkup_time       = datetime.datetime.now() - 2*checkup_interval

        zombie_interval   = datetime.timedelta(minutes=self.zombie_time)
        last_zombie_time  = datetime.datetime.now() - 2*zombie_interval

        while True:

            if datetime.datetime.now() - last_checkup_time > checkup_interval:
                self.checkForUpdate()
                last_checkup_time = datetime.datetime.now()

            if datetime.datetime.now() - last_zombie_time > zombie_interval:
                self.killZombies()
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
                zombie_interval  = datetime.timedelta(minutes = worker_count * self.zombie_time)

            sys.stdout.flush()
            self.state = 'waiting'
            self.save()
            time.sleep(waittime)

            waittime = 3600

            for self.product in self.builddata:
                for self.branch in self.builddata[self.product]:
                    for self.buildtype in self.builddata[self.product][self.branch]:
                        if self.isNewBuildNeeded(build_checkup_interval):

                            if self.tinderbox:
                                self.getTinderboxProduct()
                            else:
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

    parser.add_option('--buildspec', action='append',
                       dest='buildspecs',
                       help='Build specifiers: Restricts the builds built by '
                      'this worker to one of opt, debug, opt-asan, debug-asan. '
                      'Defaults to all build types specified in the Branches '
                      'To restrict this worker to a subset of build specifiers, '
                      'list each desired specifier in separate '
                      '--buildspec options.',
                       default=[])

    parser.add_option('--tinderbox', action='store_true',
                       dest='tinderbox',
                       help='Download latest tinderbox builds. '
                      'Defaults to False.',
                       default=False)

    (options, args) = parser.parse_args()

    exception_counter = 0

    this_worker = BuildWorker(options)

    this_worker.logMessage('starting worker %s %s %s with program dated %s' %
                          (this_worker.os_name, this_worker.os_version, this_worker.cpu_name,
                           time.ctime(program_info.programModTime)))
    while True:
        try:
            this_worker.doWork()
        except (KeyboardInterrupt, SystemExit):
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
                            this_worker.save()
                            break

            this_worker.logMessage('main: exception %s: %s' % (str(exceptionValue), errorMessage))

            time.sleep(60)


if __name__ == "__main__":
    try:
        this_worker = None
        restart = True
        main()
    except (KeyboardInterrupt, SystemExit):
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
