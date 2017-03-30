# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import glob
import httplib
import os
import platform
import random
import re
import sets
import signal
import subprocess
import sys
import time
import urllib2
import urlparse
import uuid

from bs4 import BeautifulSoup

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

os.environ['DJANGO_SETTINGS_MODULE'] = 'sisyphus.webapp.settings'

import sisyphus.webapp.settings
sisyphus_url      = os.environ["SISYPHUS_URL"]
post_files_url    = sisyphus_url + '/post_files/'

from sisyphus.webapp.bughunter import models

from sisyphus.automation import utils, program_info, crashreports
import sisyphus.automation.bugzilla

class Worker(object):

    def __init__(self, worker_type, options):

        def usr1_handler(signum, frame):
            # catch usr1 signal and terminate.
            # used when profiling to obtain a clean shutdown.
            exit(0)

        signal.signal(signal.SIGUSR1, usr1_handler)

        self.worker_type    = worker_type
        self.state          = "waiting"
        self.debug          = options.debug
        self.tinderbox      = options.tinderbox
        os.chdir(sisyphus_dir)

        try:
            self.isBuilder = options.build
            self.uploadBuild = not options.no_upload
        except AttributeError:
            self.isBuilder = False

        # Adjust the time before a worker is considered a zombie
        # to 3 hours for a builder to account for possible long build
        # times and to 30 minutes for non builders. Note this
        # assumes that each test job will not take more than 30 minutes.
        # This assumption won't hold for valgrinded unittests, or for
        # deep scan tests. XXX: FIXME.
        if self.isBuilder:
            self.zombie_time = 3
        else:
            self.zombie_time = 1

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
            #os_name = re.search('ProductName:\t(.*)', lines[0]).group(1)
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
            raise Exception("invalid os_name: %s" % (self.os_name))

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

        try:
            self.worker_row = models.Worker.objects.get(hostname = self.hostname,
                                                        worker_type = self.worker_type)
        except models.Worker.DoesNotExist:
            self.worker_row = models.Worker(hostname = self.hostname,
                                            worker_type = self.worker_type)

        # The command line option --buildspec can take a compound value
        # whose parts are separated by dashes. The first part is the
        # what is normally considered the build type: opt or debug. The
        # remaining parts specify extra details which can be used to
        # distinguish differing types of build. For example
        # opt-asan would be an opt asan build. We need to save the
        # buildspecs to the worker's row in the database in order
        # that other workers can determine which buildspecs
        # workers support when generating 0 priority jobs when
        # reproducing crashes.
        branches_rows = models.Branch.objects.all()
        buildspecs_set = set(options.buildspecs)
        if not buildspecs_set:
            buildspecs_set = set([row.buildtype for row in branches_rows])

        self.buildspecs = ','.join(buildspecs_set)

        if len(branches_rows) == 0:
            raise Exception('Branch table is empty.')

        self.save(False)

        # Create a dictionary builddata for the Branch (product, branch, version) build data
        # and three attributes for the current product, branch, buildtype
        # which will serve to control the "build_row" property which will perform lookups
        # into the builddata dictionary

        self.product   = None
        self.branch    = None
        self.buildtype = None
        self.builddata = {}

        for branch_row in branches_rows:

            if buildspecs_set and branch_row.buildtype not in buildspecs_set:
                self.debugMessage('Branch buildtype %s not in buildspecs %s' % (
                    branch_row.buildtype, self.buildspecs))
                continue

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

            try:
                self.build_row = models.Build.objects.get(build_id = self.build_id)
            except models.Build.DoesNotExist:
                if not self.isBuilder:
                    self.build_row = None
                else:
                    self.build_row = models.Build(
                        build_id       = self.build_id,
                        product        = self.product,
                        branch         = self.branch,
                        buildtype      = self.buildtype,
                        build_cpu_name = self.build_cpu_name,
                        os_name        = self.os_name,
                        os_version     = self.os_version,
                        cpu_name       = self.cpu_name,
                        worker         = self.worker_row,
                        state          = "initializing",
                        builddate      = None,
                        buildavailable = None,
                        buildsuccess   = None,
                        changeset      = None,
                        executablepath = None,
                        packagesuccess = None,
                        clobbersuccess = None,
                        )
                    self.build_row.save()

    def parse_buildspec(self, buildspec):
        parts = buildspec.split('-')
        buildtype = parts[0]
        if len(parts) > 1:
            extra = '-'.join(parts[1:])
        else:
            extra = ''
        return {'buildtype': buildtype, 'extra': extra}

    def get_build_row(self):
        try:
            return self.builddata[self.product][self.branch][self.buildtype]["build_row"]
        except KeyError:
            return None

    def set_build_row(self, value):
        self.builddata[self.product][self.branch][self.buildtype]["build_row"] = value

    build_row = property(get_build_row, set_build_row)

    def get_build_id(self):
        try:
            return self.builddata[self.product][self.branch][self.buildtype]["build_id"]
        except KeyError:
            return None

    def set_build_id(self, value):
        self.builddata[self.product][self.branch][self.buildtype]["build_id"] = value

    build_id = property(get_build_id, set_build_id)

    def get_build_date(self):
        try:
            return self.builddata[self.product][self.branch][self.buildtype]["build_date"]
        except KeyError:
            return None;

    def set_build_date(self, value):
        self.builddata[self.product][self.branch][self.buildtype]["build_date"] = value

    build_date = property(get_build_date, set_build_date)

    def save(self, check = True):

        """
        Save the current worker to the database. Check the
        """

        try:
            if not utils.getLock('sisyphus.bughunter.worker', 300):
                raise Exception('Can not obtain lock on worker table')

            if check:
                # raise models.Worker.DoesNotExist if the worker's row has been deleted
                worker_row = models.Worker.objects.get(pk = self.worker_row.id)

                # Report inconsistencies and overwrite any changes made by others but
                # don't raise an exception.
                messages = []
                if self.worker_row.worker_type != worker_row.worker_type:
                    messages.append('worker_type memory: %s, database: %s' % (self.worker_row.worker_type,
                                                                              worker_row.worker_type))
                if self.worker_row.state != worker_row.state:
                    messages.append('state memory: %s, database: %s' % (self.worker_row.state,
                                                                        worker_row.state))
                if self.worker_row.datetime - worker_row.datetime > datetime.timedelta(seconds=1):
                    messages.append('datetime memory: %s, database: %s' % (self.worker_row.datetime,
                                                                           worker_row.datetime))
                if messages:
                    self.logMessage('WorkerInconsistent: overwriting changes: %s' % ','.join(messages))

            self.worker_row.hostname    = self.hostname
            self.worker_row.worker_type = self.worker_type
            self.worker_row.os_name     = self.os_name
            self.worker_row.os_version  = self.os_version
            self.worker_row.cpu_name    = self.cpu_name
            self.worker_row.build_cpu_name = self.build_cpu_name
            self.worker_row.state       = self.state
            self.worker_row.buildspecs  = self.buildspecs
            self.worker_row.save()

        finally:
            lockDuration = utils.releaseLock('sisyphus.bughunter.worker')
            if lockDuration > datetime.timedelta(seconds=5):
                self.logMessage("Worker.save: releaseLock('sisyphus.bughunter.worker') duration: %s" % lockDuration)

    def delete(self):
        raise Exception("Can not delete worker's due to refererential integrity issues.")

    def logMessage(self, msg):

        if self.worker_row and self.worker_row.id:
            log_row = models.Log(worker   = self.worker_row,
                                 message  = utils.makeUnicodeString(msg))
            log_row.save()

            print ("%s: %s: %s" % (log_row.worker, log_row.datetime, log_row.message)).replace('\\n', '\n')
        else:
            # handle case where logMessage is called before the worker's database row has been saved/retrieved.
            print ("%s: %s" % (utils.getTimestamp(hiresolution=True), msg)).replace('\\n', '\n')

    def debugMessage(self, msg):
        if self.debug:
            self.logMessage(msg)

    def reloadProgram(self, db_available=True):

        sys.stdout.flush()
        sys.stderr.flush()
        process_dict = self.psTest()
        if process_dict:
            if self.debug:
                for pid in process_dict:
                    self.debugMessage('reloadProgram: test process still running during reloadProgram: %s' % process_dict[pid])
            self.killTest()

        # double check that everything is killed.
        process_dict = self.psTest()
        if process_dict:
            for pid in process_dict:
                self.logMessage('reloadProgram: test process still running during reloadProgram: %s' % process_dict[pid])
            self.killTest()

        self.state = 'dead'
        if db_available:
            self.save()

        utils.reloadProgram(program_info)

    def checkForUpdate(self):
        if program_info.changed():
            message = 'checkForUpdate: Program change detected. Reloading from disk. %s %s' % (sys.executable, sys.argv)
            self.logMessage(message)
            try:
                self.state = 'dead'
                self.save()
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                pass # We want to restart regardless of any error.

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
        """
        This method removes several "bogus" urls from the list which we do not
        wish to use in bugzilla queries.
        """
        exclude_urls_set = sets.Set(['startup', 'shutdown', 'automationutils.processLeakLog()', 'a blank page', ''])
        url_set = sets.Set(url_list)
        url_set.difference_update(exclude_urls_set)
        return list(url_set)

    def process_assertions(self, assertion_dict, page, test, extra_test_args):

        for key in assertion_dict:
            assertionmessage = assertion_dict[key]["message"]
            assertionfile    = assertion_dict[key]["file"]
            assertionstack   = assertion_dict[key]["stack"]
            assertioncount   = assertion_dict[key]["count"]

            # Strip the leading part of the path from assertionfile
            # in order that assertions on different branches can be
            # consolidated in the database. Otherwise the branch name
            # will result in different Assertion objects for different
            # branches even for the same assertion.
            assertionfile = re.sub(
                '(/work)?/mozilla/builds/[^/]+/mozilla/|'
                '/builds/.*/build/(src/)?|'
                '/home/worker/workspace/build/src/',
                '', assertionfile)

            assertion_rows = models.Assertion.objects.filter(
                os_name         = self.os_name,
                os_version      = self.os_version,
                cpu_name        = self.cpu_name,
                product         = self.product,
                branch          = self.branch,
                buildtype       = self.buildtype,
                build_cpu_name  = self.build_cpu_name,
                assertion       = assertionmessage,
                location        = assertionfile,
                )

            if len(assertion_rows) > 0:
                assertion_row = assertion_rows[0]
            else:
                assertion_row = models.Assertion(
                    os_name         = self.os_name,
                    os_version      = self.os_version,
                    cpu_name        = self.cpu_name,
                    product         = self.product,
                    branch          = self.branch,
                    buildtype       = self.buildtype,
                    build_cpu_name  = self.build_cpu_name,
                    assertion       = assertionmessage,
                    location        = assertionfile,
                    )
                assertion_row.save()

            testassertion_row = self.model_test_assertion(
                url                 = page,
                stack               = assertionstack,
                count               = assertioncount,
                testrun             = self.testrun_row,
                assertion           = assertion_row,
                )
            testassertion_row.save()

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

        valgrind_dict = {}

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

            valgrind_stack = match.group(0)
            valgrind_stack = re.sub(reValgrindLeader, '', valgrind_stack)
            line_match     = reLine.match(valgrind_stack)
            valgrind_msg   = line_match.group(0)

            # create a valgrind signature by replacing line numbers, hex numbers with
            # spaces for searching bugzilla with all strings query type, and taking the first
            # three lines.
            valgrind_signature = ' '.join(valgrind_stack.split('\n')[0:3])
            valgrind_signature = re.sub(reHexNumbers, '', valgrind_signature)
            valgrind_signature = re.sub(reNumbers, '', valgrind_signature)
            valgrind_signature = re.sub('\W+', ' ', valgrind_signature)
            valgrind_signature = re.sub(' {2,}', ' ', valgrind_signature)

            valgrind_msg       = valgrind_msg.strip()
            valgrind_stack     =  valgrind_stack.strip()
            valgrind_signature = valgrind_signature.strip()
            valgrind_key       = valgrind_msg + ':' + valgrind_signature + ':' + valgrind_stack
            if valgrind_key in valgrind_dict:
                valgrind_dict[valgrind_key]["count"] += 1
            else:
                valgrind_dict[valgrind_key] = {
                    "message"   : valgrind_msg,
                    "stack"     : valgrind_stack,
                    "signature" : valgrind_signature,
                    "count"     : 1,
                    }
            valgrind_text = valgrind_text[len(match.group(0)):]

        return valgrind_dict

    def process_valgrind(self, valgrind_text, page, test, extra_test_args):

        valgrind_dict = self.parse_valgrind(valgrind_text)

        for key in valgrind_dict:
            valgrind_message   = valgrind_dict[key]["message"]
            valgrind_stack     = valgrind_dict[key]["stack"]
            valgrind_signature = valgrind_dict[key]["signature"]
            valgrind_count     = valgrind_dict[key]["count"]

            if re.search('^HEAP', valgrind_signature):
                continue

            valgrind_rows = models.Valgrind.objects.filter(
                os_name         = self.os_name,
                os_version      = self.os_version,
                cpu_name        = self.cpu_name,
                product         = self.product,
                branch          = self.branch,
                buildtype       = self.buildtype,
                build_cpu_name  = self.build_cpu_name,
                signature       = valgrind_signature,
                message         = valgrind_message,
                )

            if len(valgrind_rows) > 0:
                valgrind_row = valgrind_rows[0]
            else:
                valgrind_row = models.Valgrind(
                    os_name         = self.os_name,
                    os_version      = self.os_version,
                    cpu_name        = self.cpu_name,
                    product         = self.product,
                    branch          = self.branch,
                    buildtype       = self.buildtype,
                    build_cpu_name  = self.build_cpu_name,
                    signature       = valgrind_signature,
                    message         = valgrind_message,
                    )
                valgrind_row.save()

            testvalgrind_row = self.model_test_valgrind(
                url                 = page,
                stack               = valgrind_stack,
                count               = valgrind_count,
                testrun             = self.testrun_row,
                valgrind            = valgrind_row,
                )
            testvalgrind_row.save()


    def process_asan(self, asan_list, page, uploadpath):

        if not asan_list:
            return

        self.testrun_row.crashed = True

        for asan_dict in asan_list:
            # replace each pure address frame by 0x to prevent random pure addresses from
            # polluting the signature and preventing matches.
            asansignature = ' '.join([re.sub('^@0x[0-9a-fA-F]+$', '0x', frame)
                                      for frame in asan_dict["frames"][:5]])

            crash_rows = models.Crash.objects.filter(
                os_name         = self.os_name,
                os_version      = self.os_version,
                cpu_name        = self.cpu_name,
                product         = self.product,
                branch          = self.branch,
                buildtype       = self.buildtype,
                build_cpu_name  = self.build_cpu_name,
                signature       = asansignature,
                )

            if len(crash_rows) > 0:
                crash_row = crash_rows[0]
            else:
                crash_row = models.Crash(
                    os_name         = self.os_name,
                    os_version      = self.os_version,
                    cpu_name        = self.cpu_name,
                    product         = self.product,
                    branch          = self.branch,
                    buildtype       = self.buildtype,
                    build_cpu_name  = self.build_cpu_name,
                    signature       = asansignature,
                    )
                crash_row.save()

            testcrash_row = self.model_test_crash(
                url            = page,
                exploitability = 'none' if asan_dict['reason'] == 'SEGV' else 'medium',
                reason         = asan_dict['reason'],
                address        = None,
                crashreport    = None,
                crashtype      = 'asan',
                testrun        = self.testrun_row,
                crash          = crash_row
                )
            testcrash_row.save()

            uploader = utils.FileUploader(post_files_url,
                                          self.model_test_crash.__name__,
                                          testcrash_row, testcrash_row.id,
                                          uploadpath)

            # Write the Asan message to the 'crash' report file.
            reportfile = '/tmp/%s.txt' % str(uuid.uuid4())
            filehandle = open(reportfile, 'w')
            filehandle.write(asan_dict['text'])
            filehandle.close()
            uploader.add('crashreport', os.path.basename(reportfile), reportfile, True)
            uploader.send()


    def process_dump_files(self, profilename, page, symbolsPathList, uploadpath):
        """
        process_dump_files looks for any minidumps that may have been written, parses them,
        then creates the necessary Crash, SiteTestCrash, SiteTestCrashDumpMetaData or
        UnitTestCrash, UnitTestCrash, UnitTestCrashDumpMetaData rows.
        """

        stackwalkPath = os.environ.get('MINIDUMP_STACKWALK', "/usr/local/bin/minidump_stackwalk")
        exploitablePath = os.environ.get('BREAKPAD_EXPLOITABLE', "/usr/local/bin/exploitable")

        self.debugMessage("stackwalkPath: %s, exists: %s, exploitablePath: %s, exists: %s, symbolsPathList: %s" %
                          (stackwalkPath, os.path.exists(stackwalkPath), exploitablePath, os.path.exists(exploitablePath), symbolsPathList))

        if not stackwalkPath or not os.path.exists(stackwalkPath):
            raise Exception('Worker.FatalError.MinidumpStackwalk.DoesNotExist')

        if not exploitablePath or not os.path.exists(exploitablePath) or not os.path.exists(exploitablePath):
            exploitablePath = None

        dumpFiles = glob.glob(os.path.join('/tmp', profilename, 'minidumps', '*.dmp'))
        self.debugMessage("dumpFiles: %s" % (dumpFiles))
        if len(dumpFiles) > 0:
            self.debugMessage("process_dump_files: %s: %d dumpfiles found in /tmp/%s" % (page, len(dumpFiles), profilename))

        icrashreport = 0

        for dumpFile in dumpFiles:
            icrashreport += 1
            self.debugMessage("process_dump_files: processing dump: %s" % (dumpFile))
            # collect information from the dump's extra file first
            # since it contains information about hangs, plugins, etc.
            data = ''
            extraFile = dumpFile.replace('.dmp', '.extra')
            crashReportFile = dumpFile.replace('.dmp', '.txt')
            try:
                extradict = {}
                if os.path.exists(extraFile):
                    extraFileHandle = open(extraFile, 'r')
                    for extraline in extraFileHandle:
                        data += extraline
                        extrasplit = extraline.rstrip().split('=', 1)
                        extradict[extrasplit[0]] = extrasplit[1]
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                self.logMessage('prompt_dump_files: exception processing extra: %s: %s, %s' % (extraFile,
                                                                                               exceptionValue,
                                                                                               errorMessage))

            finally:
                try:
                    extraFileHandle.close()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    pass

            # use timed_run.py to run stackwalker since it can hang.
            try:
                arglist = [
                    "python",
                    sisyphus_dir + "/bin/timed_run.py",
                    "300",
                    "-",
                    stackwalkPath,
                    dumpFile,
                    ]
                arglist.extend(symbolsPathList)

                proc = subprocess.Popen(
                    arglist,
                    preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    close_fds=True)
                crash_report, stderr = proc.communicate()
                self.debugMessage("stackwalking: stdout: %s" % (crash_report))
                self.debugMessage("stackwalking: stderr: %s" % (stderr))

                filehandle = open(crashReportFile, 'wb+')
                filehandle.write(crash_report)
                filehandle.close()
                # if the extra data fingers the plugin file but it doesn't
                # specify the plugin version, grep it from the crash report
                if ('PluginFilename' in extradict and
                    'PluginVersion' in extradict and
                    extradict['PluginFilename'] and
                    not extradict['PluginVersion']):
                    rePluginVersion = re.compile(r'0x[0-9a-z]+ \- 0x[0-9a-z]+  %s  (.*)' % extradict['PluginFilename'])

                    match = re.search(rePluginVersion, crash_report)
                    if match:
                        extradict['PluginVersion'] =  match.group(1)

            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                self.logMessage('process_dump_files: exception processing dump crash report: %s, %s, %s' % (dumpFile,
                                                                                                            exceptionValue,
                                                                                                            errorMessage))
            exploitability = None
            if exploitablePath:
                try:
                    proc = subprocess.Popen(
                        [
                            "python",
                            sisyphus_dir + "/bin/timed_run.py",
                            "300",
                            "-",
                            exploitablePath,
                            dumpFile,
                            ],
                        preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        close_fds=True)
                    exploitable_report, stderr = proc.communicate()
                    self.debugMessage("exploitable: stdout: %s" % (exploitable_report))
                    self.debugMessage("exploitable: stderr: %s" % (stderr))

                    reExploitability = re.compile(r'exploitability: (.*)')

                    match = re.search(reExploitability, exploitable_report)
                    if match:
                        exploitability =  match.group(1)
                    else:
                        exploitability = 'unknown'

                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    exceptionType, exceptionValue, errorMessage = utils.formatException()
                    self.logMessage('process_dump_files: exception processing dump exploitability: %s, %s, %s' % (dumpFile,
                                                                                                                  exceptionValue,
                                                                                                                  errorMessage))

            self.testrun_row.crashed = True

            crash_data = crashreports.parse_crashreport(crash_report)

            # Augment the exploitable tool by attempting to use the
            # crash address and registers of the crashing frame to
            # detect anomolous memory patterns. If the eip register
            # contains a bad value, treat the crash as exploitable
            # high, otherwise treat it as medium.
            #
            # Windows
            # http://msdn.microsoft.com/en-us/library/aa270812%28VS.60%29.aspx
            # http://msdn.microsoft.com/en-us/library/bebs9zyz.aspx
            # http://www.softwareverify.com/memory-bit-patterns.php
            # http://www.nobugs.org/developer/win32/debug_crt_heap.html
            #
            # uninitialized stack memory       0xcc
            # uninitialzed heap memory         0xcd
            # guard for aligned heap memory    0xab
            # guard for unaligned heap memory  0xfd
            # freed memory                     0xdd
            # uninitialized heap               0xbaadf00d, 0xf00dbaad (HeapAlloc)
            # freed memory                     0xfeeefeee (HeapFree)
            #
            # Mac OS X builds are run under MallocScribble.
            # https://developer.apple.com/library/mac/#documentation/Performance/Conceptual/ManagingMemory/Articles/MallocDebug.html#//apple_ref/doc/uid/20001884-CJBJFIDD
            # freed memory                     0x55
            # uninitialized memory             0xaa
            #
            # Mozilla
            # http://mxr.mozilla.org/mozilla-central/source/js/public/Utility.h#70
            # #define JS_FREE_PATTERN          0xda
            # Another value used to poison data in various locations is 0xdb.
            #
            # http://mxr.mozilla.org/mozilla-central/source/nsprpub/lib/ds/plarena.h#145
            # #define PL_FREE_PATTERN          0xda
            #
            # http://mxr.mozilla.org/mozilla-central/source/js/src/jshash.cpp#154
            # deleted hash table?              0xdb
            # Miscellaneous
            # deleted memory?                  0xdeadbeef, 0xbeefdead
            #
            # http://searchfox.org/mozilla-central/source/memory/jemalloc/moz.build#74
            # jemalloc alloc 0xe4
            # jemalloc free  0xe5

            if 'frames' in crash_data and len(crash_data['frames']) > 0:
                frame = crash_data['frames'][0]
                if 'frame_address' in frame:
                    # Check the crash address using a partial match
                    # ignoring leading 0xf or 0x0 and only requiring 3
                    # successive matches of the underlying pattern.
                    reAddressPartial = re.compile(r'0x((f|0)*((cc){3,}|(cd){3,}|(ab){3,}|(fd){3,}|(dd){3,}|(da){3,}|(db){3,}|(aa){3,}|(55){3,}|(e5){3,}|(e4){3,}|baadf00d|f00dbaad|feeefeee|deadbeef|beefdead))')
                    address = frame['frame_address']
                    match = reAddressPartial.match(address)
                    if match and exploitability != 'high' and exploitability != 'medium':
                        exploitability = 'low'
                if 'frame_registers' in frame:
                    # Check the registers using an exact match ignoring leading 0xf
                    frame_registers = frame['frame_registers']
                    reAddressExact = re.compile(r'0x((f|0)*((cc)+|(cd)+|(ab)+|(fd)+|(dd)+|(da)+|(db)+|(aa)+|(55)+|baadf00d|f00dbaad|feeefeee|deadbeef|beefdead)$)')
                    for register in frame_registers:
                        address = frame_registers[register]
                        match = reAddressExact.match(address)
                        if not match:
                            pass
                        elif register == 'eip' or register == 'rip':
                            exploitability = 'high'
                        elif exploitability != 'high':
                            exploitability = 'medium'

            # replace each pure address frame by 0x to prevent random pure addresses from
            # polluting the signature and preventing matches.
            crashsignature = ' '.join([re.sub('^@0x[0-9a-fA-F]+$', '0x', sig) for sig in crash_data["signature_list"]])

            self.debugMessage('process_dump_files: signature: %s, exploitability: %s' % (crashsignature, exploitability))

            crash_rows = models.Crash.objects.filter(
                os_name         = self.os_name,
                os_version      = self.os_version,
                cpu_name        = self.cpu_name,
                product         = self.product,
                branch          = self.branch,
                buildtype       = self.buildtype,
                build_cpu_name  = self.build_cpu_name,
                signature       = crashsignature,
                )

            if len(crash_rows) > 0:
                crash_row = crash_rows[0]
            else:
                crash_row = models.Crash(
                    os_name         = self.os_name,
                    os_version      = self.os_version,
                    cpu_name        = self.cpu_name,
                    product         = self.product,
                    branch          = self.branch,
                    buildtype       = self.buildtype,
                    build_cpu_name  = self.build_cpu_name,
                    signature       = crashsignature,
                    )
                crash_row.save()

            if 'PluginFilename' in extradict:
                pluginfilename = extradict['PluginFilename']
            else:
                pluginfilename = None

            if 'PluginVersion' in extradict:
                pluginversion = extradict['PluginVersion']
            else:
                pluginversion = None

            crashtype = 'browser'
            if 'FlashProcessDump' in extradict:
                crashtype = extradict['FlashProcessDump']
            elif 'ProcessType' in extradict:
                crashtype = extradict['ProcessType']

            try:
                reason = crash_data["crash_reason"]
            except KeyError:
                reason = 'Unknown'

            try:
                address = crash_data["crash_address"]
            except KeyError:
                address = 'Unknown'

            testcrash_row = self.model_test_crash(
                url            = page,
                exploitability = exploitability,
                reason         = reason,
                address        = address,
                crashreport    = None,
                crashtype      = crashtype,
                pluginfilename = pluginfilename,
                pluginversion  = pluginversion,
                testrun        = self.testrun_row,
                crash          = crash_row
                )
            testcrash_row.save()

            uploader = utils.FileUploader(post_files_url,
                                          self.model_test_crash.__name__, testcrash_row, testcrash_row.id,
                                          uploadpath)
            if os.path.exists(dumpFile):
                uploader.add('minidump', os.path.basename(dumpFile), dumpFile, True)

            if os.path.exists(extraFile):
                uploader.add('extradump', os.path.basename(extraFile), extraFile)

            if os.path.exists(crashReportFile):
                uploader.add('crashreport', os.path.basename(crashReportFile), crashReportFile, True)

            if os.path.exists(dumpFile) or os.path.exists(extraFile) or os.path.exists(crashReportFile):
                testcrash_row = uploader.send()

            for extraproperty in extradict:
                if extraproperty != 'ServerURL':
                    testcrashdumpmeta_row = self.model_test_crash_dump_meta_data(
                        key = extraproperty,
                        value = extradict[extraproperty],
                        crash = testcrash_row
                        )
                    testcrashdumpmeta_row.save()


    def killZombies(self):
        """ zombify any *other* worker of the same type who has not updated status in zombie_time hours"""

        try:
            if not utils.getLock('sisyphus.bughunter.worker', 300):
                self.logMessage('killZombies: failed to lock crash workers. better luck next time.')
                return

            zombie_timestamp = datetime.datetime.now() - datetime.timedelta(hours=self.zombie_time)
            worker_rows      = models.Worker.objects.filter(worker_type__exact = self.worker_type)
            worker_rows      = models.Worker.objects.filter(datetime__lt = zombie_timestamp)
            worker_rows      = worker_rows.filter(state__in = ('waiting',
                                                               'building',
                                                               'installing',
                                                               'executing',
                                                               'testing',
                                                               'completed'))
            worker_rows      = worker_rows.exclude(pk = self.worker_row.id)
            zombie_count     = worker_rows.update(state = 'zombie')
            if zombie_count > 0:
                self.logMessage("killZombies: worker %s zombied %d workers" % (self.hostname, zombie_count))

        finally:
            lockDuration = utils.releaseLock('sisyphus.bughunter.worker')
            if lockDuration > datetime.timedelta(seconds=5):
                self.logMessage("killZombies: releaseLock('sisyphus.bughunter.worker') duration: %s" % lockDuration)


    def getBuild(self):

        try:
            # Attempt to get a native build for this cpu.
            build_row = models.Build.objects.get(build_id = self.build_id)
        except models.Build.DoesNotExist:
            build_row = None

        return build_row

    def isBuildClaimed(self):
        # Return True if the current row in the Build table has been
        # claimed by another worker.
        #
        # A build is claimed by another worker if its worker is
        # different than this worker and if its state is not building.
        # This will prevent conflicts between two different build
        # workers with the same operating system and build_cpu_name.

        current_build_row = self.getBuild()
        if (current_build_row.worker_id == self.build_row.worker_id or
            current_build_row.state != 'building'):
            return False

        return True

    def saveBuild(self):

        if not self.isBuilder:
            raise Exception('WorkerNotBuilder')

        if not self.isBuildClaimed():
            self.build_row.save()

    def installBuild(self):

        self.build_date = None # Mark us as not having a local build.
        self.state = 'installing'
        self.save()

        if not self.build_row or not self.build_row.buildavailable:
            self.logMessage('installBuild: build not available %s %s %s' %
                            (self.product, self.branch, self.buildtype))
            return False

        self.logMessage("begin installing %s %s %s" % (self.product, self.branch, self.buildtype))

        # clobber old build to make sure we don't mix builds.
        # note clobber essentially rm's the objdir.
        if not self.clobberProduct():
            return False

        # XXX: Do we need to generalize this?
        buildspec = self.parse_buildspec(self.buildtype)
        if buildspec['extra']:
            branch = '%s-%s' % (self.branch, buildspec['extra'])
        else:
            branch = self.branch

        objdir = '/mozilla/builds/%s/mozilla/%s-%s' % (branch, self.product, buildspec['buildtype'])

        productfilename = os.path.basename(self.build_row.product_package)

        if self.os_name == 'Windows NT':
            objsubdir = '/dist/bin'
        elif self.os_name == 'Mac OS X':
            objsubdir = '/dist'
        elif self.os_name == 'Linux':
            objsubdir = '/dist/bin'
        else:
            raise Exception('installBuild: unsupported operating system: %s' % self.os_name)

        build_uri_prefix = sisyphus.webapp.settings.SISYPHUS_URL + '/media/builds/'
        producturi = build_uri_prefix + '/' + productfilename

        if not utils.downloadFile(producturi, '/tmp/' + productfilename):
            self.logMessage('installBuild: failed to download %s %s %s failed' %
                            (self.product, self.branch, self.buildtype))
            return False

        # install-build.sh -p product -b branch -x objdir/dist/bin -f /tmp/productfilename
        cmd = [sisyphus_dir + "/bin/install-build.sh", "-p", self.product, "-b", self.branch,
               "-x", objdir + objsubdir, "-f", "/tmp/" + productfilename]

        proc = subprocess.Popen(cmd,
                                preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, close_fds=True)
        try:
            stdout = proc.communicate()[0]
            if os.path.exists('/tmp/' + productfilename):
                os.unlink('/tmp/' + productfilename)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('installBuild: exception: %s, %s' % (exceptionValue, errorMessage))

            if errorMessage.find('filedescriptor out of range') != -1:
                self.logMessage('filedescriptors %d out of range. Restarting.' %
                                utils.openFileDescriptorCount())
                # Closing file descriptors and trying again does not
                # fix the issue on Windows. Just restart the program.
                self.reloadProgram()

        if proc.returncode != 0:
            self.logMessage('installBuild: install-build.sh %s %s %s failed: %s' %
                            (self.product, self.branch, self.buildtype, stdout))
            return False

        if buildspec['extra'] != 'asan':
            # asan builds don't have symbols
            symbolsfilename = os.path.basename(self.build_row.symbols_file)
            symbolsuri = build_uri_prefix + '/' + symbolsfilename
            if not utils.downloadFile(symbolsuri, '/tmp/' + symbolsfilename):
                self.logMessage('installBuild:  %s %s %s failed to download symbols %s' %
                                (self.product, self.branch, self.buildtype, symbolsfilename))
                return False

            # use command line since ZipFile.extractall isn't available until Python 2.6
            # unzip -d /objdir/dist/crashreporter-symbols /tmp/symbolsfilename
            os.mkdir(objdir + '/dist/crashreporter-symbols')
            cmd = ["unzip", "-d", objdir + "/dist/crashreporter-symbols", "/tmp/" + symbolsfilename]
            proc = subprocess.Popen(cmd,
                                    preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            try:
                stdout = proc.communicate()[0]
                if os.path.exists('/tmp/' + symbolsfilename):
                    os.unlink('/tmp/' + symbolsfilename)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                self.logMessage('installBuild: exception: %s, %s' % (exceptionValue, errorMessage))

                if errorMessage.find('filedescriptor out of range') != -1:
                    self.logMessage('filedescriptors %d out of range. Restarting.' %
                                    utils.openFileDescriptorCount())
                    # Closing file descriptors and trying again does not
                    # fix the issue on Windows. Just restart the program.
                    self.reloadProgram()

            if proc.returncode != 0:
                self.logMessage('installBuild: unzip crashreporter-symbols.zip %s %s %s failed: %s' %
                                (self.product, self.branch, self.buildtype, stdout))
                return False

        self.logMessage("success installing %s %s %s" % (self.product, self.branch, self.buildtype))

        self.build_date = self.build_row.builddate

        return True

    def isNewBuildNeeded(self, build_checkup_interval):
        """
        Checks the current state of the build information to determine if a new build
        needs to be created and uploaded or to be downloaded and installed.
        """

        try:
            if not utils.getLock('sisyphus.bughunter.build', 300):
                raise Exception('Can not obtain lock on build table')

            if self.build_row:
                # We already have a build row, we just need to update it.
                self.build_row = models.Build.objects.get(build_id = self.build_id)
            else:
                try:
                    self.build_row = models.Build.objects.get(build_id = self.build_id)
                except models.Build.DoesNotExist:
                    return True

            if self.isBuilder:

                if not self.build_date:
                    return True # Don't have a local build

                if self.build_row.state == "error":
                    return True # Most recent attempt to build and upload to database failed

                if self.build_date.day != datetime.date.today().day:
                    return True # Local build is too old

                if self.build_row.builddate.day != datetime.date.today().day:
                    return True # Uploaded build is too old

                if self.build_row.state == "building":
                    # someone else is building it.
                    if datetime.datetime.now() - self.build_row.datetime > build_checkup_interval:
                        # Overwrite and steal build from other worker.
                        self.build_row.worker = self.worker_row
                        self.build_row.state  = 'error'
                        self.build_row.build_cpu_name = self.build_cpu_name
                        self.build_row.os_name = self.os_name
                        self.build_row.os_version = self.os_version
                        self.build_row.cpu_name = self.cpu_name
                        self.build_row.worker_id = self.worker_row.id
                        self.build_row.save()
                        return True # the build has been "in process" for too long. Consider it dead.

                return False

            # We are not a builder
            if not self.build_date:
                return True # Don't have a local build

            if self.build_date < self.build_row.builddate:
                return True # Available build from database is newer than the local build

        finally:
            lockDuration = utils.releaseLock('sisyphus.bughunter.build')
            if lockDuration > datetime.timedelta(seconds=5):
                self.logMessage("Worker.isNewBuildNeeded: releaseLock('sisyphus.bughunter.build') duration: %s" % lockDuration)

        return False

    def get_remote_text(self, url):
        """Return the string containing the contents of a remote url if the
        HTTP response code is 200, otherwise return None.

        :param url: url of content to be retrieved.
        """
        conn = None

        try:
            scheme = urlparse.urlparse(url).scheme
            if not scheme:
                raise Exception('required scheme missing in url %s' % url)

            while True:
                conn = urllib2.urlopen(url)
                code = conn.getcode()
                if code == 200:
                    content = conn.read()
                    return content
                if code != 503:
                    self.logMessage("Unable to open url %s : %s" % (
                        url, httplib.responses[code]))
                    return None
                # Server is too busy. Wait and try again.
                # See https://bugzilla.mozilla.org/show_bug.cgi?id=1146983#c10
                self.logMessage("HTTP 503 Server Too Busy: url %s" % url)
                conn.close()
                time.sleep(60 + random.randrange(0,30,1))
        except Exception, e:
            self.logMessage('%s Unable to open %s' % (e, url))
            return None
        finally:
            if conn:
                conn.close()

        return content

    # lifted from mozregression:utils.py:urlLinks/autophone
    def url_links(self, url):
        """Return list of all non-navigation links found in web page.

        arguments:
        url - location of web page.

        returns: list of BeautifulSoup links.
        """
        content = self.get_remote_text(url)
        if not content:
            return []

        soup = BeautifulSoup(content, 'html.parser')
        # do not return a generator but an array, so we can store it for later use
        return [link for link in soup.findAll('a')
                if not link.get('href').startswith('?') and
                link.get_text() != 'Parent Directory']

    def get_build_url(self, directory, build_regex):
        self.debugMessage('get_build_url: searching directory %s' % directory)

        # Ensure directory ends with a trailing /.
        # See https://docs.python.org/2.7/library/os.path.html#os.path.join
        directory = os.path.join(directory, '')

        self.debugMessage('Checking directory %s...' % directory)

        build_links = self.url_links(directory)
        for build_link in build_links:
            filename = build_link.get_text()
            self.debugMessage('find_builds_by_directory: checking filename: %s' % filename)
            if build_regex.match(filename):
                self.debugMessage('find_builds_by_directory: found filename: %s' % filename)
                return '%s%s' % (directory, filename)
        self.logMessage('No builds found in %s.' % directory)
        return None

    def getTinderboxProduct(self):
        buildchangeset  = None
        buildsuccess    = True
        builddate       = datetime.datetime.now()
        executablepath  = ''

        try:
            if not utils.getLock('sisyphus.bughunter.build', 300):
                raise Exception('Can not obtain lock on build table')

            self.state = "building"
            self.build_date = None
            # use worker's build_date to signify availability of local build
            # and to determine freshness of the uploaded build
            self.save()

            self.build_row.state = "building"
            self.build_row.build_cpu_name = self.build_cpu_name
            self.build_row.os_name = self.os_name
            self.build_row.os_version = self.os_version
            self.build_row.cpu_name = self.cpu_name
            self.build_row.worker_id = self.worker_row.id
            self.saveBuild()
        finally:
            lockDuration = utils.releaseLock('sisyphus.bughunter.build')
            if lockDuration > datetime.timedelta(seconds=5):
                self.logMessage("getTinderboxProduct: releaseLock('sisyphus.bughunter.build') duration: %s" % lockDuration)

        # kill any test processes still running.
        self.killTest()

        self.logMessage("get build %s %s %s" % (self.product, self.branch, self.buildtype))

        buildspec = self.parse_buildspec(self.buildtype)

        args =  [
            sisyphus_dir + "/bin/set-build-env.sh",
            "-p", self.product,
            "-b", self.branch,
            "-T", buildspec['buildtype'],
            "-c", "set",
            ]
        if buildspec['extra']:
            args.extend(['-e', buildspec['extra']])

        if self.cpu_name != self.build_cpu_name:
            if self.build_cpu_name == "x86":
                build_cpu_name = "intel32"
            elif self.build_cpu_name == "x86_64":
                build_cpu_name = "intel64"
            else:
                build_cpu_name = self.build_cpu_name
            args.extend(["-X", build_cpu_name])

        proc = subprocess.Popen(
            args,
            preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True)

        try:
            stdout = proc.communicate()[0]
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('getTinderboxProduct: exception: %s, %s' % (exceptionValue, errorMessage))

            if errorMessage.find('filedescriptor out of range') != -1:
                self.logMessage('filedescriptors %d out of range. Restarting.' %
                                utils.openFileDescriptorCount())
                # Closing file descriptors and trying again does not
                # fix the issue on Windows. Just restart the program.
                self.reloadProgram()

        reFatalError = re.compile(r'FATAL ERROR')
        reExecutablePath = re.compile(r'executablepath=(.*)', flags=re.I)
        logs = stdout.split('\n')
        for logline in logs:

            if reFatalError.match(logline):
                self.logMessage(logline)
                buildsuccess = False
                break

            matchexecutablepath = reExecutablePath.match(logline)
            if matchexecutablepath:
                executablepath = matchexecutablepath.group(1)
            if executablepath:
                break

        if not executablepath:
            self.logMessage('failed to get executablepath')
            buildsuccess = False

        self.debugMessage('getTinderboxBuild: set-build-env: %s' % stdout)

        if not buildsuccess:
            self.build_row.builddate      = builddate
            self.build_row.buildavailable = False # unavailable until packaged and uploaded.
            self.build_row.buildsuccess   = buildsuccess
            self.build_row.changeset      = buildchangeset
            self.build_row.executablepath = executablepath
            self.build_row.uploadsuccess  = None
            self.build_row.state = "error"
            self.saveBuild()
            return

        # Download build, get changeset.
        #
        build_file_pattern = self.product + '.*'
        build_file_ext = ''

        tinderbox_prefix = 'https://archive.mozilla.org/pub/firefox/tinderbox-builds'
        tinderbox_repo_name = ''
        if self.branch == 'nightly':
            tinderbox_repo_name = 'mozilla-central'
        elif self.branch == 'aurora':
            tinderbox_repo_name = 'mozilla-aurora'
        elif self.branch == 'beta':
            tinderbox_repo_name = 'mozilla-beta'
        else:
            raise Exception('getTinderboxBuild: Unknown branch %s' % self.branch)

        taskcluster_bits = '32'
        tinderbox_os_bits = ''
        if self.os_name == 'Linux':
            tinderbox_os_bits = '-linux' + ('64' if self.cpu_name == 'x86_64' else '')
            build_file_pattern += '\.linux-' + ('x86_64' if self.cpu_name == 'x86_64' else 'i686')
            build_file_ext = 'tar.bz2'
        elif self.os_name == 'Mac OS X':
            tinderbox_os_bits = '-macosx64'
            build_file_pattern += '\.mac(64)?'
            build_file_ext = 'dmg'
        elif self.os_name == 'Windows NT':
            tinderbox_os_bits = '-win' + ('64' if self.cpu_name == 'x86_64' else '32')
            build_file_pattern += 'win' + ('64' if self.cpu_name == 'x86_64' else '32')
            build_file_ext = 'zip'
        else:
            raise Exception('getTinderboxBuild: Unknown os %s' % self.os_name)

        if tinderbox_os_bits.endswith('64'):
            taskcluster_bits = '64'

        tinderbox_extra = ''
        if buildspec['extra']:
            tinderbox_extra = buildspec['extra']
            build_file_pattern += '-' + buildspec['extra']

        build_file_pattern = '(' + build_file_pattern + '|target).' + build_file_ext
        build_regex = re.compile(build_file_pattern)

        tinderbox_debug = ''
        if buildspec['buildtype'] == 'debug':
            tinderbox_debug = '-debug'

        task_id = utils.find_latest_task_id(tinderbox_repo_name,
                                            self.os_name,
                                            taskcluster_bits,
                                            buildspec['buildtype'],
                                            buildspec['extra'],
                                            log=self.debugMessage)
        build_url = utils.find_build_by_task_id(task_id, build_regex, log=self.debugMessage)
        if not build_url:
            self.logMessage('getTinderboxBuild: no builds found: '
                            'repo: %s, os_name: %s, bits: %s, build_type: %s, extra: %s' %
                            (tinderbox_repo_name, self.os_name, taskcluster_bits,
                            buildspec['buildtype'], buildspec['extra']))

            # The links from the tinderbox directory are returned in date
            # order. Currently, the last link is to the obsolete "latest"
            # directory which means that currently the latest timestamp is
            # the second to last entry. When the latest link is removed in
            # the future, the latest timestamp will be the last entry.
            tinderbox_dir = '%s/%s%s%s%s/' % (
                tinderbox_prefix,
                tinderbox_repo_name,
                tinderbox_os_bits,
                tinderbox_extra,
                tinderbox_debug)

            re_timestamp = re.compile('[0-9]+')
            build_links = self.url_links(tinderbox_dir)
            while build_links and not build_url:
                build_link = build_links[-1]
                text = build_link.get_text().strip('/')
                if re_timestamp.match(text):
                    build_dir = '%s%s/' % (tinderbox_dir, text)
                    build_url = self.get_build_url(build_dir, build_regex)
                build_links = build_links[:-1]
            if not build_url:
                self.logMessage('getTinderboxBuild: no builds found at %s' %
                                tinderbox_dir)
                buildsuccess = False

        if buildsuccess and not self.isBuildClaimed():
            uploader = utils.FileUploader(post_files_url,
                                          'Build', self.build_row, self.build_row.build_id,
                                          'builds')
            # Download the product package
            fieldname = 'product_package'
            filename = '%s.%s' % (self.build_id, build_file_ext)
            build_path = '/tmp/' + filename
            symbols_path = None
            if not utils.downloadFile(build_url, build_path):
                self.logMessage('getTinderboxBuild: failed to download %s' %
                                build_url)
                buildsuccess = False
            else:
                # Add the product package to the uploader
                uploader.add(fieldname, filename, build_path)
                if buildspec['extra'] != 'asan':
                    # asan builds do not have separate symbols file
                    symbols_url = build_url.replace(build_file_ext, 'crashreporter-symbols.zip')
                    fieldname = 'symbols_file'
                    filename = '%s.crashreporter-symbols.zip' % self.build_row.build_id
                    symbols_path = '/tmp/' + filename
                    if not utils.downloadFile(symbols_url, symbols_path):
                        self.logMessage('getTinderboxBuild: failed to download %s' %
                                        symbols_url)
                        buildsuccess = False
                    else:
                        # Add the crash symbols to the uploader
                        uploader.add(fieldname, filename, symbols_path)
                        self.logMessage('success uploading %s %s %s' % (self.product, self.branch, self.buildtype))
                if buildsuccess:
                    self.build_row = uploader.send()

            if os.path.exists(build_path):
                os.unlink(build_path)
            if symbols_path and os.path.exists(symbols_path):
                os.unlink(symbols_path)

        self.build_row.builddate      = builddate
        self.build_row.buildavailable = buildsuccess
        self.build_row.buildsuccess   = buildsuccess
        self.build_row.changeset      = buildchangeset
        self.build_row.executablepath = executablepath
        self.build_row.uploadsuccess  = None

        if buildsuccess:
            self.build_row.state = "complete"
            self.build_date = builddate
            self.logMessage("success getting  %s" % build_url)
        else:
            self.build_row.state = "error"
            self.logMessage("failure getting %s" % build_url)

        self.saveBuild()


    def buildProduct(self):
        buildsteps      = "clobber checkout build"
        buildchangeset  = None
        buildsuccess    = True
        checkoutlogpath = ''
        buildlogpath    = ''
        builddate       = datetime.datetime.now()
        executablepath  = ''

        try:
            if not utils.getLock('sisyphus.bughunter.build', 300):
                raise Exception('Can not obtain lock on build table')

            self.state = "building"
            self.build_date = None
            # use worker's build_date to signify availability of local build
            # and to determine freshness of the uploaded build
            self.save()

            self.build_row.state = "building"
            self.build_row.build_cpu_name = self.build_cpu_name
            self.build_row.os_name = self.os_name
            self.build_row.os_version = self.os_version
            self.build_row.cpu_name = self.cpu_name
            self.build_row.worker_id = self.worker_row.id
            self.saveBuild()
        finally:
            lockDuration = utils.releaseLock('sisyphus.bughunter.build')
            if lockDuration > datetime.timedelta(seconds=5):
                self.logMessage("Worker.buildProduct: releaseLock('sisyphus.bughunter.build') duration: %s" % lockDuration)

        # kill any test processes still running.
        self.killTest()

        self.logMessage("begin building %s %s %s" % (self.product, self.branch, self.buildtype))

        buildspec = self.parse_buildspec(self.buildtype)

        builder_command_list =  [
            sisyphus_dir + "/bin/builder.sh",
            "-p", self.product,
            "-b", self.branch,
            "-T", buildspec['buildtype'],
            "-B", buildsteps
            ]
        if buildspec['extra']:
            builder_command_list.extend(['-e', buildspec['extra']])

        if self.cpu_name != self.build_cpu_name:
            if self.build_cpu_name == "x86":
                build_cpu_name = "intel32"
            elif self.build_cpu_name == "x86_64":
                build_cpu_name = "intel64"
            else:
                build_cpu_name = self.build_cpu_name
            builder_command_list.extend(["-X", build_cpu_name])

        proc = subprocess.Popen(
            builder_command_list,
            preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True)

        try:
            stdout = proc.communicate()[0]
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('buildProduct: exception: %s, %s' % (exceptionValue, errorMessage))

            if errorMessage.find('filedescriptor out of range') != -1:
                self.logMessage('filedescriptors %d out of range. Restarting.' %
                                utils.openFileDescriptorCount())
                # Closing file descriptors and trying again does not
                # fix the issue on Windows. Just restart the program.
                self.reloadProgram()

        reFatalError = re.compile(r'FATAL ERROR')
        reExecutablePath = re.compile(r'environment: executablepath=(.*)')

        logs = stdout.split('\n')
        for logline in logs:

            if reFatalError.match(logline):
                buildsuccess = False

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
                            buildchangeset = matchchangeset.group(1).split(' ')[0]
                        if buildchangeset:
                            break
                    logfile.close()
                buildlogmatch = re.search('build.log', logpath)
                if buildlogmatch:
                    buildlogpath = logpath
                    logfile = open(logpath, 'rb')
                    for line in logfile:
                        matchexecutablepath = reExecutablePath.match(line)
                        if matchexecutablepath:
                            executablepath = matchexecutablepath.group(1)
                        if executablepath:
                            break
                    logfile.close()
                clobberlogmatch = re.search('clobber.log', logpath)
                if clobberlogmatch:
                    os.unlink(logpath)

        self.build_row.builddate      = builddate
        self.build_row.buildavailable = False # unavailable until packaged and uploaded.
        self.build_row.buildsuccess   = buildsuccess
        self.build_row.changeset      = buildchangeset
        self.build_row.executablepath = executablepath
        self.build_row.uploadsuccess  = None

        if buildsuccess:
            self.build_row.state = "complete"
            self.logMessage("success building %s %s %s changeset %s" % (self.product, self.branch, self.buildtype, buildchangeset))
        else:
            self.build_row.state = "error"
            self.logMessage("failure building %s %s %s changeset %s" % (self.product, self.branch, self.buildtype, buildchangeset))

        if not self.isBuildClaimed():
            uploader = utils.FileUploader(post_files_url,
                                          'Build', self.build_row, self.build_row.build_id,
                                          'builds')

            if checkoutlogpath:
                uploader.add('checkout_log', os.path.basename(checkoutlogpath), checkoutlogpath, True)

            if buildlogpath:
                uploader.add('build_log', os.path.basename(buildlogpath), buildlogpath, True)

            if checkoutlogpath or buildlogpath:
                self.build_row = uploader.send()

        if buildsuccess:
            self.build_date = builddate

        self.saveBuild()

    def clobberProduct(self):
        """
        Call Sisyphus to clobber the build.
        """
        clobbersuccess = True
        clobberlogpath = ''
        buildspec = self.parse_buildspec(self.buildtype)
        if buildspec['extra']:
            branch = '%s-%s' % (self.branch, buildspec['extra'])
        else:
            branch = self.branch

        objdir = "/mozilla/builds/%s/mozilla/%s-%s" % (
            branch,
            self.product,
            buildspec['buildtype'])

        if not os.path.exists(objdir):
            return True

        self.logMessage("begin clobbering %s %s %s" % (self.product, self.branch, self.buildtype))

        proc = subprocess.Popen(
            [
                "rm",
                "-fR",
                objdir
                ],
            preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        try:
            stdout = proc.communicate()[0]
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('clobberProduct: exception: %s, %s' % (exceptionValue, errorMessage))

            if errorMessage.find('filedescriptor out of range') != -1:
                self.logMessage('filedescriptors %d out of range. Restarting.' %
                                utils.openFileDescriptorCount())
                # Closing file descriptors and trying again does not
                # fix the issue on Windows. Just restart the program.
                self.reloadProgram()

        if proc.returncode != 0:
            clobbersuccess = False

        clobberlogpath = None
        logs = stdout.split('\n')
        for logline in logs:
            logpathmatch = re.search('log: (.*clobber\.log)', logline)
            if logpathmatch:
                clobberlogpath = logpathmatch.group(1)

        if clobbersuccess:
            self.logMessage('success clobbering %s %s %s' % (self.product, self.branch, self.buildtype))
        else:
            self.logMessage('failure clobbering %s %s %s' % (self.product, self.branch, self.buildtype))

        self.build_row.clobbersuccess = clobbersuccess

        if not self.isBuildClaimed() and clobberlogpath:
            uploader = utils.FileUploader(post_files_url,
                                          'Build', self.build_row, self.build_row.build_id,
                                          'builds')
            uploader.add('clobber_log', os.path.basename(clobberlogpath), clobberlogpath, True)
            self.build_row = uploader.send()

        return clobbersuccess

    def packageProduct(self):
        packagesuccess = True
        buildspec = self.parse_buildspec(self.buildtype)

        self.logMessage('begin packaging %s %s %s' % (self.product, self.branch, self.buildtype))

        # remove any stale package files
        executablepath = self.build_row.executablepath
        productfiles = glob.glob(os.path.join(executablepath, self.product + '-*'))
        for productfile in productfiles:
            os.unlink(productfile)

        # SYM_STORE_SOURCE_DIRS= required due to bug 534992
        # XXX: Do not package-tests since:
        # a) they are not used in bughunter
        # b) tests do not currently build for the beta/12 branch under vc2010
        #    due to the Moz_Assert/JS_Assert confusion there.
        args = [
                sisyphus_dir + "/bin/set-build-env.sh",
                "-p", self.product,
                "-b", self.branch,
                "-T", buildspec['buildtype'],
                "-c", "$MAKE -C firefox-%s package buildsymbols SYM_STORE_SOURCE_DIRS=" % (buildspec['buildtype'])
                ]

        if buildspec['extra']:
            args.extend(['-e', buildspec['extra']])

        proc = subprocess.Popen(
            args,
            preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        try:
            packagelogtext = proc.communicate()[0]
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('packageProduct: exception: %s, %s' % (exceptionValue, errorMessage))

            if errorMessage.find('filedescriptor out of range') != -1:
                self.logMessage('filedescriptors %d out of range. Restarting.' %
                                utils.openFileDescriptorCount())
                # Closing file descriptors and trying again does not
                # fix the issue on Windows. Just restart the program.
                self.reloadProgram()

        if proc.returncode != 0:
            packagesuccess = False

        if packagesuccess:
            self.logMessage('success packaging %s %s %s' % (self.product, self.branch, self.buildtype))
        else:
            self.logMessage('failure packaging %s %s %s' % (self.product, self.branch, self.buildtype))

        self.build_row.packagesuccess = packagesuccess

        packagelogpath = ''
        if packagelogtext:
            packagelogpath = '/tmp/package.log'
            packagelog = open(packagelogpath, 'wb+')
            packagelog.write(packagelogtext)
            packagelog.close()

        if not self.isBuildClaimed() and packagelogpath:
            uploader = utils.FileUploader(post_files_url,
                                          'Build', self.build_row, self.build_row.build_id,
                                          'builds')
            uploader.add('package_log', self.build_row.build_id + '-package.log', packagelogpath, True)
            self.build_row = uploader.send()

    def uploadProduct(self):

        if self.isBuildClaimed():
            return

        self.logMessage('begin uploading %s %s %s' % (self.product, self.branch, self.buildtype))

        executablepath = self.build_row.executablepath

        if not os.path.exists(executablepath):
            self.logMessage('executablepath %s does not exist' % executablepath)

        if not os.path.isdir(executablepath):
            self.logMessage('executablepath %s is not a directory' % executablepath)


        filepaths = glob.glob(os.path.join(executablepath, self.product + '-*'))
        if len(filepaths) == 0:
            self.logMessage('executablepath %s does not contain product files %s-*' % (executablepath, self.product))

        uploader = utils.FileUploader(post_files_url,
                                      'Build', self.build_row, self.build_row.build_id,
                                      'builds')

        for filepath in filepaths:
            filepathbasename = os.path.basename(filepath)

            if re.search('\.crashreporter-symbols-full\.zip$', filepathbasename):
                fieldname = 'symbols_file'
                filename = "%s.crashreporter-symbols.zip" % self.build_row.build_id
            elif re.search('\.crashreporter-symbols\.zip$', filepathbasename):
                fieldname = 'symbols_file'
                filename = "%s.crashreporter-symbols.zip" % self.build_row.build_id
            elif re.search('\.tests.zip$', filepathbasename):
                fieldname = 'tests_file'
                filename = "%s.tests.zip" % self.build_row.build_id
            elif re.search('\.tests.tar.bz2$', filepathbasename):
                fieldname = 'tests_file'
                filename = "%s.tests.tar.bz2" % self.build_row.build_id
            elif re.search('\.zip$', filepathbasename):
                fieldname = 'product_package'
                filename = "%s.zip" % self.build_row.build_id
            elif re.search('\.tar.bz2$', filepathbasename):
                fieldname = 'product_package'
                filename = "%s.tar.bz2" % self.build_row.build_id
            elif re.search('\.dmg$', filepathbasename):
                fieldname = 'product_package'
                filename = "%s.dmg" % self.build_row.build_id
            else:
                continue

            uploader.add(fieldname, filename, filepath)

        uploadsuccess = False

        self.build_row = uploader.send()

        uploadsuccess = True # XXX: redundant?

        if uploadsuccess:
            self.logMessage('success uploading %s %s %s' % (self.product, self.branch, self.buildtype))
        else:
            self.build_row.state = "error"
            self.logMessage('failure uploading %s %s %s' % (self.product, self.branch, self.buildtype))

        self.build_row.uploadsuccess  = uploadsuccess
        self.build_row.buildavailable = uploadsuccess
        self.build_row.state          = "complete"
        self.build_row.worker         = self.worker_row
        self.build_row.save()

    def publishNewBuild(self):

        try:
            self.buildProduct()
            if not self.build_row.buildsuccess:
                # automatically clobber if a build fails
                self.clobberProduct()
            else:
                self.packageProduct()
                if self.build_row.packagesuccess and self.uploadBuild:
                    self.uploadProduct()

        except (KeyboardInterrupt, SystemExit):
            self.build_date      = None
            self.build_row.state = "error"
            self.build_row.save()
            raise

        except:
            self.build_date      = None
            self.build_row.state = "error"
            self.build_row.save()
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            self.logMessage('publishNewBuild: finishing build document %s %s %s: %s' %
                            (self.product, self.branch, self.buildtype, errorMessage))

    def psTest(self):
        # ps test processes
        process_dict = {}

        if self.os_name != "Windows NT":
            pattern = r' *([0-9]+)\s+.*((/work)?/mozilla/builds/[^/]+/mozilla/' + self.product + '-' + self.buildtype + '|totem-plugin-viewer|gst-install-plugins-helper)'
            ps_args = ['ps', '-e', '-x']
        else:
            # use the Windows process id which is more reliable in killing
            # stuck processes.
            pattern = r' *[0-9]+\s+[0-9]+\s+[0-9]+\s+([0-9]+)\s+.*((/work)?/mozilla/builds/[^/]+/mozilla/' + self.product + '-' + self.buildtype + '|mozilla-build|java|wmplayer|mplayer2|wmpnetwk|Windows Media Player)'
            ps_args = ['ps', 'aux']

        ps_proc = subprocess.Popen(ps_args,
                                   preexec_fn=lambda : os.setpgid(0,0), # make the process its own process group
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = ps_proc.communicate()
        ps_lines = stdout.split('\n')
        for ps_line in ps_lines:
            ps_line = ps_line.replace('\\', '/')
            ps_match = re.match(pattern, ps_line)
            if ps_match and 'ssh-agent' not in ps_line:
                pid = ps_match.group(1)
                try:
                    int(pid)
                except ValueError:
                    self.logMessage("psTest: Invalid pid %s: line: %s" % (pid, ps_line))
                process_dict[pid] = ps_line

        return process_dict

    def killTest(self, test_pid = None):
        # os.kill fails to kill the entire test process and children when
        # a test times out. This is most noticible on Windows but can occur on
        # Linux as well. To kill the test reliably, use the external kill program
        # to kill all test processes.
        #
        # First repeatedly attempt to kill the test processes by
        # searching for them using ps, then killing them individually
        # using /bin/kill.  Then attempt to kill the test process and
        # the test process group directly using os.kill and os.killpg.
        #
        # I've chosen this order since performing the waitpid on windows
        # can hang, thus preventing the worker from completing the kill
        # task.

        process_dict = self.psTest()
        pids = [pid for pid in process_dict]
        if len(pids) > 0:
            for attempt in range(4):
                # Repeatedly attempt to kill the test processes.
                # If we can not kill the test processes, raise an
                # Exception('Worker.killTest.FatalError').
                for pid in process_dict:
                    self.logMessage("killTest: attempt %d: %s" % (attempt, process_dict[pid].rstrip()))

                if self.os_name != "Windows NT":
                    kill_args = ["/bin/kill", "-9"]
                else:
                    kill_args = ["/bin/kill", "-f", "-9"]

                kill_args.extend(pids)
                subprocess.call(kill_args)

                try:
                    time.sleep(5)
                except KeyboardInterrupt:
                    pass

                process_dict = self.psTest()
                pids = [pid for pid in process_dict]

                if len(pids) == 0:
                    break

        if test_pid is not None:
            # Note: our calls to Popen used preexec_fn to set the process group of the
            # Popened process to the same value as the child's pid.
            try:
                self.logMessage("killTest: os.kill(%d, 9)" % test_pid)
                os.kill(test_pid, 9)
            except OSError, oserror:
                if oserror.errno == 3:
                    pass # No such process
                elif oserror.errno == 10:
                    pass # No child process
                elif oserror.errno == 32:
                    pass # Broken pipe
                else:
                    exceptionType, exceptionValue, errorMessage = utils.formatException()
                    self.logMessage('killTest: os.kill: %s: %s, %s' % (exceptionType,
                                                                       exceptionValue,
                                                                       errorMessage))
            try:
                self.logMessage("killTest: os.killpg(%d, 9)" % test_pid)
                os.killpg(test_pid, 9)
            except OSError, oserror:
                if oserror.errno == 3:
                    pass # No such process
                elif oserror.errno == 10:
                    pass # No child process
                elif oserror.errno == 32:
                    pass # Broken pipe
                else:
                    exceptionType, exceptionValue, errorMessage = utils.formatException()
                    self.logMessage('killTest: os.killpg: %s: %s, %s' % (exceptionType,
                                                                         exceptionValue,
                                                                         errorMessage))
            try:
                (wait_pid, wait_status) = os.waitpid(-1, os.WNOHANG)
                self.logMessage('killTest: pid: %s, waitpid(-1, os.WNOHANG) == (%s, %s)' % (test_pid, wait_pid, wait_status))
            except OSError, oserror:
                if oserror.errno == 3:
                    pass # No such process
                elif oserror.errno == 10:
                    pass # No child process
                elif oserror.errno == 32:
                    pass # Broken pipe
                else:
                    exceptionType, exceptionValue, errorMessage = utils.formatException()
                    self.logMessage('killTest: os.killpg: %s: %s, %s' % (exceptionType,
                                                                         exceptionValue,
                                                                         errorMessage))
        process_dict = self.psTest()
        pids = [pid for pid in process_dict]

        if len(pids) > 0:
            for pid in process_dict:
                self.logMessage("killTest: unable to kill %s" % process_dict[pid].rstrip())
            raise Exception('Worker.killTest.FatalError')


