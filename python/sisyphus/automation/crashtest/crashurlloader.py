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
import sys
import re
import urlparse
import datetime
import time

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

from django.db import connection

from sisyphus.automation import utils
import sisyphus.webapp.settings
from sisyphus.webapp.bughunter import models

def main():

    usage = '''usage: %prog [options] --urls urls.list --signature signature
'''
    parser = OptionParser(usage=usage)

    parser.add_option('-s', '--skipurls', action='store', type='string',
                      dest='skipurlsfile',
                      default=None,
                      help='file containing url patterns to skip when uploading.')

    parser.add_option('--urls', action='store', type='string',
                      dest='urlsfile',
                      default=None,
                      help='file containing url patterns to skip when uploading.')

    parser.add_option('--signature', action='store', type='string',
                      dest='signature',
                      default=None,
                      help='set the signature document\'s signature' +
                      'property to allow tracking of this set of urls.')

    (options, args) = parser.parse_args()

    if not options.urlsfile:
        parser.error('urls.list file is required')

    if not options.signature:
        parser.error('signature is required')

    skipurls = []
    if options.skipurlsfile:
        skipurlsfilehandle = open(options.skipurlsfile, 'r')
        for skipurl in skipurlsfilehandle:
            skipurl = skipurl.rstrip('\n')
            skipurls.append(skipurl)
        skipurlsfilehandle.close()

    branches_rows = models.Branch.objects.all()

    if len(branches_rows) == 0:
        raise Exception('Branch table is empty.')

    operating_systems = {}

    matching_worker_rows  = models.Worker.objects.filter(worker_type__exact = 'crashtest')

    if len(matching_worker_rows) == 0:
        print "There are no workers to use to determine operating systems for the jobs"
        exit(1)

    for worker_row in matching_worker_rows:
        if worker_row.state == 'disabled':
            continue

        os_name    = worker_row.os_name
        os_version = worker_row.os_version
        cpu_name   = worker_row.cpu_name
        build_cpu_name = worker_row.build_cpu_name

        if os_name not in operating_systems:
            operating_systems[os_name] = {}

        if os_version not in operating_systems[os_name]:
            operating_systems[os_name][os_version] = {}

        if cpu_name not in operating_systems[os_name][os_version]:
            operating_systems[os_name][os_version][cpu_name] = {}

        if build_cpu_name not in operating_systems[os_name][os_version][cpu_name]:
            operating_systems[os_name][os_version][cpu_name][build_cpu_name] = 1

    rePrivateNetworks = re.compile(r'https?://(localhost|127\.0\.0\.1|192\.168\.[0-9]+\.[0-9]+|172\.16\.[0-9]+\.[0-9]+|10\.[0-9]+\.[0-9]+\.[0-9]+)')

    starttime = datetime.datetime.now()
    url_counter = 0
    nonhttp_counter = 0
    private_counter = 0
    badurl_counter = 0
    skip_counter = 0
    unsupported_counter = 0
    socorro_counter = 0
    testrun_counter = 0
    locktimeout = 300
    waittime = 30
    locktime = datetime.timedelta(seconds=30)

    # lock the table to prevent contention with running workers.
    while not utils.getLock('sisyphus.bughunter.sitetestrun', locktimeout):
        continue
    lasttime = datetime.datetime.now()

    urlsfilehandle = open(options.urlsfile, 'r')
    try:
        for url in urlsfilehandle:

            url_counter += 1

            # temporarily unlock the table to allow workers processing time.
            if datetime.datetime.now() - lasttime > locktime:
                utils.releaseLock('sisyphus.bughunter.sitetestrun')
                time.sleep(waittime)
                while not utils.getLock('sisyphus.bughunter.sitetestrun', locktimeout):
                    continue
                lasttime = datetime.datetime.now()

            url = url.rstrip('\n')
            if url.find('http') != 0:
                nonhttp_counter += 1
                continue # skip non-http urls

            match = rePrivateNetworks.match(url)
            if match:
                private_counter += 1
                continue # skip private networks

            try:
                url = utils.encodeUrl(url)
            except Exception, e:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                print '%s, %s: url: %s' % (exceptionValue, errorMessage, url)
                badurl_counter += 1
                continue

            for skipurl in skipurls:
                if re.search(skipurl, url):
                    skip_counter += 1
                    continue

            for branch_row in branches_rows:
                product       = branch_row.product
                branch        = branch_row.branch
                major_version = branch_row.major_version
                buildtype     = branch_row.buildtype

                for os_name in operating_systems:
                    for os_version in operating_systems[os_name]:
                        for cpu_name in operating_systems[os_name][os_version]:

                            # PowerPC is not supported after Firefox 3.6
                            if major_version > '0306' and cpu_name == 'ppc':
                                unsupported_counter += 1
                                continue

                            for build_cpu_name in operating_systems[os_name][os_version][cpu_name]:
                                # 64 bit builds are not fully supported for
                                # 1.9.2 on Mac OS X 10.6

                                if (branch == "1.9.2" and
                                    os_name == "Mac OS X" and
                                    os_version == "10.6" and
                                    build_cpu_name == "x86_64"):
                                    unsupported_counter += 1
                                    continue

                                socorro_row = models.SocorroRecord(
                                    signature           = options.signature,
                                    url                 = url,
                                    uuid                = '',
                                    client_crash_date   = None,
                                    date_processed      = None,
                                    last_crash          = None,
                                    product             = branch_row.product,
                                    version             = '',
                                    build               = '',
                                    branch              = branch_row.branch,
                                    os_name             = os_name,
                                    os_full_version     = os_version,
                                    os_version          = os_version,
                                    cpu_info            = cpu_name,
                                    cpu_name            = cpu_name,
                                    address             = '',
                                    bug_list            = '',
                                    user_comments       = '',
                                    uptime_seconds      = None,
                                    adu_count           = None,
                                    topmost_filenames   = '',
                                    addons_checked      = '',
                                    flash_version       = '',
                                    hangid              = '',
                                    reason              = '',
                                    process_type        = '',
                                    app_notes           = '',
                                    )

                                try:
                                    socorro_row.save()
                                    socorro_counter += 1
                                    test_run = models.SiteTestRun(
                                        os_name           = os_name,
                                        os_version        = os_version,
                                        cpu_name          = cpu_name,
                                        product           = product,
                                        branch            = branch,
                                        buildtype         = buildtype,
                                        build_cpu_name    = build_cpu_name,
                                        worker            = None,
                                        socorro           = socorro_row,
                                        changeset         = None,
                                        major_version     = major_version,
                                        bug_list          = None,
                                        crashed           = False,
                                        extra_test_args   = None,
                                        steps             = '',
                                        fatal_message     = None,
                                        exitstatus        = None,
                                        log               = None,
                                        priority          = '1',
                                        state             = 'waiting',
                                        )
                                    test_run.save()
                                    testrun_counter += 1
                                except Exception, e:
                                    print "Exception: %s, url: %s" % (e, url)
    finally:
        try:
            lockDuration = utils.releaseLock('sisyphus.bughunter.sitetestrun')
            print(("loaded %d urls; eliminated %d unsupported records, %d non http urls, " +
                   "%d private urls, %d bad urls, %d skipped urls; uploaded %d socorro records, " +
                   "%d testruns in %s") %
                  ( url_counter,
                    unsupported_counter,
                    nonhttp_counter,
                    private_counter,
                    badurl_counter,
                    skip_counter,
                    socorro_counter,
                    testrun_counter,
                    datetime.datetime.now() - starttime
                    ))
        except:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            print '%s, %s' % (exceptionValue, errorMessage)

    urlsfilehandle.close()

if __name__ == '__main__':
    main()
