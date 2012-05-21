# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

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
import sisyphus.automation.worker

options          = None

class UserWorker(sisyphus.automation.worker.Worker):

    def save(self):
        pass

    def debugMessage(self, msg):
        if self.debug:
            print ("%s: %s" % (utils.getTimestamp(hiresolution=True), msg)).replace('\\n', '\n')

    def logMessage(self, msg):
        print ("%s: %s" % (utils.getTimestamp(hiresolution=True), msg)).replace('\\n', '\n')

    def __init__(self, options):
        options.build = False
        self.worker_type    = "user"
        self.state          = "waiting"
        self.debug          = options.debug

        os.chdir(sisyphus_dir)

        self.isBuilder = False
        self.uploadBuild = False
        self.zombie_time = 99

        uname           = os.uname()
        self.os_name    = uname[0]
        self.hostname   = uname[1]
        self.os_version = uname[2]
        self.cpu_name   = uname[-1]

        if self.os_name.find("Linux") != -1:
            self.os_name = "Linux"
            self.os_id   = 'linux'
            self.os_version = re.search('([0-9]+\.[0-9]+\.[0-9]+).*', self.os_version).group(1)
            os.environ["MOZ_X_SYNC"]="1"
        elif self.os_name.find("Darwin") != -1:
            self.os_name = "Mac OS X"
            self.os_id   = 'darwin'
            proc = subprocess.Popen(["sw_vers"],
                                    preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout,stderr = proc.communicate()
            lines = stdout.split('\n')
            self.os_version = re.search('ProductVersion:\t([0-9]+\.[0-9]+).*', lines[1]).group(1)
        elif self.os_name.find("CYGWIN") != -1:
            self.os_name = "Windows NT"
            self.os_id   = 'nt'
            proc = subprocess.Popen(["cygcheck", "-s"],
                                    preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            stdout,stderr = proc.communicate()
            lines = stdout.split('\r\n')
            self.os_version = re.search('.* Ver ([^ ]*) .*', lines[4]).group(1)
        else:
            raise Exception("invalid os_name: %s" % (os_name))

        if self.os_name == "Windows NT":
            if "PROCESSOR_ARCHITEW6432" in os.environ and os.environ["PROCESSOR_ARCHITEW6432"]:
                self.cpu_name = "x86_64"
            else:
                self.cpu_name = "x86"
        else:
            bits = platform.architecture()[0]
            if self.cpu_name == "i386" or self.cpu_name == "i686":
                if bits == "32bit":
                    self.cpu_name = "x86"
                elif bits == "64bit":
                    self.cpu_name = "x86_64"
            elif self.cpu_name == 'Power Macintosh':
                self.cpu_name = 'ppc'

        # self.build_cpu_name is the cpu type where the builds that are to be run were created.
        if options.processor_type:
            if options.processor_type == 'intel32' or options.processor_type == 'amd32':
                self.build_cpu_name = 'x86'
            elif options.processor_type == 'intel64' or options.processor_type == 'amd64':
                self.build_cpu_name = 'x86_64'
            else:
                self.build_cpu_name = options.processor_type
        else:
            self.build_cpu_name = self.cpu_name

        # Create a dictionary builddata for the Branch (product, branch, version) build data
        # and three attributes for the current product, branch, buildtype
        # which will serve to control the "build_row" property which will perform lookups
        # into the builddata dictionary

        self.product   = None
        self.branch    = None
        self.buildtype = None
        self.builddata = {}

        branches_rows = models.Branch.objects.all()

        if len(branches_rows) == 0:
            raise Exception('Branch table is empty.')

        for branch_row in branches_rows:

            self.product   = branch_row.product
            self.branch    = branch_row.branch
            self.buildtype = branch_row.buildtype

            if self.product not in self.builddata:
                self.builddata[self.product] = {}

            if self.branch not in self.builddata[self.product]:
                self.builddata[self.product][self.branch] = {}

            if self.buildtype not in self.builddata[self.product][self.branch]:
                self.builddata[self.product][self.branch][self.buildtype] = {}

            self.build_id =  "%s_%s_%s_%s_%s" % (self.product, self.branch, self.buildtype,
                                                 self.os_name.replace(' ', '_'),
                                                 self.build_cpu_name)

            # Treat missing build as fatal and let exception propagate
            self.build_row = models.Build.objects.get(build_id = self.build_id)

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

    parser.add_option('--processor-type', action='store', type='string',
                       dest='processor_type',
                       help='Override default processor type: intel32, intel64, amd32, amd64',
                       default=None)

    (options, args) = parser.parse_args()

    try:
        this_worker = UserWorker(options)
        for this_worker.product in this_worker.builddata:
            for this_worker.branch in this_worker.builddata[this_worker.product]:
                for this_worker.buildtype in this_worker.builddata[this_worker.product][this_worker.branch]:
                    this_worker.installBuild()

    except Exception, e:
        print e


if __name__ == "__main__":
    main()
    print 'Program terminating'


