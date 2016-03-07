# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import re
import requests
import sys

from optparse import OptionParser

if __name__ == '__main__':
    sisyphus_dir = os.environ["SISYPHUS_DIR"]
    tempdir = os.path.join(sisyphus_dir, 'python')
    if tempdir not in sys.path:
        sys.path.append(tempdir)

    tempdir = os.path.join(tempdir, 'sisyphus')
    if tempdir not in sys.path:
        sys.path.append(tempdir)

    tempdir = os.path.join(tempdir, 'webapp')
    if tempdir not in sys.path:
        sys.path.append(tempdir)

    os.environ['DJANGO_SETTINGS_MODULE'] = 'sisyphus.webapp.settings'

    import django
    django.setup()

from django.db import connection
from sisyphus.automation import utils
from sisyphus.webapp.bughunter import models


class CrashLoader(object):
    rePrivateNetworks = re.compile(r'https?://(' +
                                   'localhost|' +
                                   '[^./]+\.localdomain|' +
                                   '[^./]+\.local|' +
                                   '[^./]+($|/)|' +
                                   '127\.0\.0\.1|' +
                                   '192\.168\.[0-9]+\.[0-9]+|' +
                                   '172\.16\.[0-9]+\.[0-9]+|' +
                                   '10\.[0-9]+\.[0-9]+\.[0-9]+' +
                                   ')')
    def __init__(self):
        self.skipurls = []
        self.products = {}
        self.versions = {}
        self.branches = {}
        self.buildtypes = {}
        self.operating_systems = {}
        self.load_products()
        self.load_operating_systems()

    def load_products(self):
        """Load Product data from the Branch table.

        The Branch table (id, product, branch, major_version, buildtype)
        maps Product versions to branches and supported buildtypes. For
        example, as of today,

        id     product     branch  major_version buildtype
        14     firefox     1.9.2   0306          debug
        13     firefox     beta    0600          debug
        10     firefox     beta    0700          debug
        11     firefox     aurora  0800          debug
        12     firefox     nightly 0900          debug

        The branch for SiteTestRun rows for an incoming SocorroRecord is
        determined by retrieving the branch corresponding to the
        SocorroRecord's major_version. Since the major_version to branch
        mapping is many-one, we use the convention that the major_version
        corresponding to a particual branch is the largest value for that
        branch.

        In our example, Firefox versions 6 and 7 are tested using the beta
        branch.  The version of the beta branch, at the time of this
        table, corresponds to the highest major_value for the beta branch
        which is 0700.
        """
        self.branches_rows = models.Branch.objects.all()

        if len(self.branches_rows) == 0:
            raise Exception('Branch table is empty.')

        for branch_row in self.branches_rows:
            product = branch_row.product
            self.products[product] = 1
            if product not in self.buildtypes:
                self.buildtypes[product] = {}
            if product not in self.versions:
                self.versions[product] = {}
            if product not in self.branches:
                self.branches[product] = {}
            self.buildtypes[product][branch_row.buildtype] = 1
            self.versions[product][branch_row.major_version] = branch_row.branch
            if branch_row.branch not in self.branches[product]:
                self.branches[product][branch_row.branch] = branch_row.major_version
            elif branch_row.major_version > self.branches[product][branch_row.branch]:
                self.branches[product][branch_row.branch] = branch_row.major_version

    def load_operating_systems(self):
        worker_rows  = models.Worker.objects.filter(worker_type__exact = 'crashtest')

        if len(worker_rows) == 0:
            raise Exception("There are no workers to use to determine operating systems for the jobs")

        for worker_row in worker_rows:
            if worker_row.state == 'disabled' or worker_row.state == 'zombie':
                continue

            os_name    = worker_row.os_name
            os_version = worker_row.os_version
            cpu_name   = worker_row.cpu_name
            build_cpu_name = worker_row.build_cpu_name

            if os_name not in self.operating_systems:
                self.operating_systems[os_name] = {}

            if os_version not in self.operating_systems[os_name]:
                self.operating_systems[os_name][os_version] = {}

            if cpu_name not in self.operating_systems[os_name][os_version]:
                self.operating_systems[os_name][os_version][cpu_name] = {}

            buildspecs = set(worker_row.buildspecs.split(','))
            if build_cpu_name not in self.operating_systems[os_name][os_version][cpu_name]:
                self.operating_systems[os_name][os_version][cpu_name][build_cpu_name] = buildspecs
            else:
                self.operating_systems[os_name][os_version][cpu_name][build_cpu_name] = self.operating_systems[os_name][os_version][cpu_name][build_cpu_name].union(buildspecs)

    def ordered_ffversion(self, versionstring):
         versionstring = re.sub('[a-z].*$', '', versionstring)
         version = ''
         versionparts = re.split('[.]*', versionstring)
         for i in range(0,len(versionparts)):
             try:
                 version += ( '00' +  versionparts[i] )[-2:]
             except:
                 break # ignore and terminate

         return version

    def load_waiting_testruns(self):

        waiting_testruns = {}

        cursor = connection.cursor()
        if cursor.execute("SELECT SocorroRecord.url, " +
                          "SiteTestRun.os_name, " +
                          "SiteTestRun.os_version, " +
                          "SiteTestRun.cpu_name, " +
                          "SiteTestRun.build_cpu_name, " +
                          "SiteTestRun.branch, " +
                          "SiteTestRun.product, " +
                          "SiteTestRun.buildtype " +
                          "FROM SocorroRecord, SiteTestRun WHERE " +
                          "SiteTestRun.socorro_id = SocorroRecord.id AND " +
                          "SiteTestRun.state = 'waiting'"):
            row = cursor.fetchone()
            while row is not None:
                key = "%s:%s:%s:%s:%s:%s:%s:%s" % (
                    row[0], # url
                    row[1], # os_name
                    row[2], # os_version
                    row[3], # cpu_name
                    row[4], # build_cpu_name
                    row[5], # branch
                    row[6], # product
                    row[7]  # buildtype
                    )

                waiting_testruns[key] = 1
                row = cursor.fetchone()

        return waiting_testruns

    def load_socorro_crashdata(self, start_date, stop_date, include_hangs):

        pending_socorro = {}

        results_offset = 0
        results_number = 1000
        #
        crashes = [{}] # seed dummy entry for initial loop entry

        headers = {'Auth-Token': os.environ['SISYPHUS_SOCORRO_API_TOKEN'] }

        while crashes:
            url = 'https://crash-stats.mozilla.com/api/SuperSearchUnredacted/'
            payload = {
                'url': '!__null__',
                'url': '!',
                '_facets': 'signature',
                '_columns': ['date',
                             'signature',
                             'product',
                             'version',
                             'build_id',
                             'release_channel',
                             'platform',
                             'platform_version',
                             'cpu_info',
                             'cpu_arch',
                             'url',
                             'exploitability'],
                'date': ['>=%s' % start_date, '<=%s' % stop_date],
                '_results_offset': results_offset,
                '_results_number': results_number
            }

            response = requests.get(url, headers=headers, params=payload)

            try:
                crash_data = response.json()
                results_offset += results_number
                crashes = crash_data['hits']
            except ValueError, e:
                crashes = []
                print 'Exception %s Response %s' % (e, response.__dict__)
                return pending_socorro

            for crash in crashes:
                signature         = crash['signature']
                url               = crash['url'] if 'url' in crash else ''
                if not url:
                    continue
                url               = url[:1000] # XXX Should get this from the model
                product           = crash['product']
                version           = crash['version']
                build             = crash['build_id']
                branch            = crash['release_channel']
                os_name           = crash['platform']
                os_version        = crash['platform_version']
                os_full_version   = os_version
                cpu_info          = crash['cpu_info']
                cpu_name          = crash['cpu_arch']

                # Firefox -> firefox
                product    = product.lower()

                # fennec -> firefox
                if product not in self.products:
                    product = 'firefox'

                # 6.1.7601 Service Pack 1 -> 6.1
                os_version = '.'.join(os_full_version.split('.')[0:2])

                # convert wyciwyg urls
                url = re.sub(r'wyciwyg://[0-9]+/', '', url)

                if url.find('http') != 0:
                    continue # skip non-http urls

                match = self.rePrivateNetworks.match(url)
                if match:
                    continue # skip private networks

                if signature.find('hang ') == 0 and not include_hangs:
                    # ignore hang signatures since their urls are
                    # duplicate in the matched crash signature.
                    continue

                try:
                    url = utils.encodeUrl(url)
                except Exception, e:
                    exceptionType, exceptionValue, errorMessage = utils.formatException()
                    print '%s, %s: url: %s' % (exceptionValue, errorMessage, url)
                    continue

                skipit = False
                for skipurl in self.skipurls:
                    if re.search(skipurl, url):
                        skipit = True
                        break

                if skipit:
                    continue

                minor_version = self.ordered_ffversion(version)
                major_version = minor_version[0:4]

                if not major_version in self.versions[product]:
                    continue # skip unsupported major versions

                if version.find('4.0') == 0 and build < '20100101':
                    continue # Ignore bogus version 4

                # The branch data from socorro is unreliable as it depends
                # on data entry which is notoriously wrong. However the
                # version number is guaranteed to be correct. Create the branch
                # information from the Branch table.
                branch = self.versions[product][major_version]

                # We currently do not have AMD processors so we will map them
                # to Intel processors. This also takes care of the case where 
                # we misreport Intel 64 bit processors as AMD.
                match = re.match(r'.*amd(32|64)', cpu_name)
                if match:
                    cpu_name = 'x86'
                    if match.group(1) == '64':
                        cpu_name += '_64'

                socorro_row = models.SocorroRecord(
                    signature               = utils.crash_report_field2string(signature),
                    url                     = url,
                    product                 = product,
                    version                 = version,
                    build                   = build,
                    branch                  = branch,
                    os_name                 = utils.crash_report_field2string(os_name),
                    os_full_version         = utils.crash_report_field2string(os_full_version),
                    os_version              = utils.crash_report_field2string(os_version),
                    cpu_info                = utils.crash_report_field2string(cpu_info),
                    cpu_name                = utils.crash_report_field2string(cpu_name),
                    )

                key = "%s:%s:%s:%s:%s:%s" % (
                    socorro_row.url,
                    socorro_row.os_name,
                    socorro_row.os_version,
                    socorro_row.cpu_name,
                    socorro_row.branch,
                    socorro_row.product
                    )

                if key not in pending_socorro:
                    pending_socorro[key] = socorro_row

        return pending_socorro

    def load_urls(self, urls, user_id, signature):

        pending_socorro = {}

        for url in urls:

            if url.find('http') != 0:
                continue # skip non-http urls

            match = self.rePrivateNetworks.match(url)
            if match:
                continue # skip private networks

            try:
                url = utils.encodeUrl(url)
            except Exception:
                exceptionType, exceptionValue, errorMessage = utils.formatException()
                print '%s, %s: url: %s' % (exceptionValue, errorMessage, url)
                continue

            skipit = False
            for skipurl in self.skipurls:
                if re.search(skipurl, url):
                    skipit = True
                    break

            if skipit:
                continue

            for branch_row in self.branches_rows:
                product       = branch_row.product
                branch        = branch_row.branch
                major_version = branch_row.major_version

                for os_name in self.operating_systems:
                    for os_version in self.operating_systems[os_name]:
                        for cpu_name in self.operating_systems[os_name][os_version]:

                            # PowerPC is not supported after Firefox 3.6
                            if major_version > '0306' and cpu_name == 'ppc':
                                continue

                            for build_cpu_name in self.operating_systems[os_name][os_version][cpu_name]:
                                # 64 bit builds are not fully supported for
                                # 1.9.2 on Mac OS X 10.6

                                if (branch == "1.9.2" and
                                    os_name == "Mac OS X" and
                                    os_version == "10.6" and
                                    build_cpu_name == "x86_64"):
                                    continue

                                socorro_row = models.SocorroRecord(
                                    signature           = signature,
                                    url                 = url,
                                    product             = product,
                                    branch              = branch_row.branch,
                                    os_name             = os_name,
                                    os_full_version     = os_version,
                                    os_version          = os_version,
                                    cpu_info            = cpu_name,
                                    cpu_name            = cpu_name,
                                    user_id             = user_id
                                    )

                                key = "%s:%s:%s:%s:%s:%s" % (
                                    socorro_row.url,
                                    socorro_row.os_name,
                                    socorro_row.os_version,
                                    socorro_row.cpu_name,
                                    socorro_row.branch,
                                    socorro_row.product
                                    )

                                if key not in pending_socorro:
                                    pending_socorro[key] = socorro_row
        return pending_socorro

    def create_socorro_rows(self, pending_socorro, waiting_testruns, priority):

        socorro_keys = [socorro_key for socorro_key in pending_socorro]

        for socorro_key in socorro_keys:

            socorro_row = pending_socorro[socorro_key]

            del pending_socorro[socorro_key]

            # Instead of making the workers determine the best possible
            # match for a job, we will now create the jobs to match the
            # available workers. This is no longer non-determinstic but
            # will cover each unknown by the full set of possible worker
            # types. NOTE: This requires a representative sample of
            # workers be available when the jobs are loaded.

            product       = socorro_row.product
            os_name       = socorro_row.os_name
            os_version    = socorro_row.os_version
            cpu_name      = socorro_row.cpu_name
            branch        = socorro_row.branch
            major_version = self.branches[product][branch]

            operating_systems = {}
            if os_name in self.operating_systems:
                if os_version in self.operating_systems[os_name]:
                    operating_systems[os_name] = {}
                    operating_systems[os_name][os_version] = {}
                    if cpu_name in self.operating_systems[os_name][os_version]:
                        # We have an exact match on os_name, os_version and cpu_name,
                        # however the reported cpu_name in Socorro is the cpu_name of
                        # the build (build_cpu_name) and not necessarily the cpu_name
                        # of the physical machine. We need to create a job for the
                        # operating system, version and each possible physical cpu/build cpu
                        # represented by our workers.
                        operating_systems[os_name][os_version] = {}
                        operating_systems[os_name][os_version][cpu_name] = dict(self.operating_systems[os_name][os_version][cpu_name])
                    else:
                        # We have a match on the operating system and version but not the cpu,
                        # create jobs for this operating system and version and for each
                        # available cpu
                        operating_systems[os_name][os_version] = dict(self.operating_systems[os_name][os_version])
                else:
                    # We have a match on the operating system but not the version,
                    # create jobs for this operating system and for each of the available
                    # versions and cpus
                    operating_systems[os_name] = dict(self.operating_systems[os_name])
            else:
                # We do not have a match on the operating system,
                # create jobs for each of the available operating systems, versions and cpus
                operating_systems = dict(self.operating_systems)

            # Only save the SocorroRecord if the corresponding SiteTestRun
            # is saved. Therefore wait until we save the SiteTestRun to
            # save the SocorroRow.
            socorro_row_saved = False

            for os_name in operating_systems:
                for os_version in operating_systems[os_name]:
                    for cpu_name in operating_systems[os_name][os_version]:
                        for build_cpu_name in operating_systems[os_name][os_version][cpu_name]:
                            buildspecs = self.operating_systems[os_name][os_version][cpu_name][build_cpu_name]

                            for buildtype in self.buildtypes[product]:

                                if buildtype not in buildspecs:
                                    continue

                                key = "%s:%s:%s:%s:%s:%s:%s:%s" % (
                                    socorro_row.url,
                                    os_name,
                                    os_version,
                                    cpu_name,
                                    build_cpu_name,
                                    branch,
                                    product,
                                    buildtype
                                    )

                                if key in waiting_testruns:
                                    continue

                                # 64 bit builds are not fully supported for 1.9.2 on Mac OS X 10.6
                                if (branch == "1.9.2" and
                                    os_name == "Mac OS X" and
                                    os_version == "10.6" and
                                    build_cpu_name == "x86_64"):
                                    continue

                                try:
                                    if not socorro_row_saved:
                                        socorro_row.save()
                                        socorro_row_saved = True

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
                                        priority          = priority,
                                        state             = 'waiting',
                                        )
                                    try:
                                        test_run.save()
                                        waiting_testruns[key] = 1
                                        if test_run.socorro is None:
                                            print "SiteTestRun id = %s has a Null saved related SocorroRecord" % test_run.id
                                    except Exception, e:
                                        print "%s saving SiteTestRun: %s, %s : %s : %s : %s : %s : %s" % (
                                            e,
                                            socorro_row.url,
                                            test_run.os_name,
                                            test_run.os_version,
                                            test_run.cpu_name,
                                            test_run.build_cpu_name,
                                            test_run.branch,
                                            test_run.product
                                            )

                                except Exception, e:
                                    print "%s saving SoccoroRecord: %s, %s : %s : %s : %s : %s" % (
                                        e,
                                        socorro_row.url,
                                        socorro_row.os_name,
                                        socorro_row.os_version,
                                        socorro_row.cpu_name,
                                        socorro_row.branch,
                                        socorro_row.product
                                        )


def main():
    global options

    usage = '''usage: %prog [options]

Load urls into Bughunter either from Socorro or from a file containing
one url per line. By default, %prog will load urls from Socorro unless
the --urls option is specified.

Example:
%prog --start-date 2015-07-20T00:00:00 --stop-date 2015-07-20T01:00:00
'''
    parser = OptionParser(usage=usage)

    parser.add_option('--skipurls', action='store', type='string',
                      dest='skipurlsfile',
                      default=None,
                      help='File containing url patterns to skip when uploading.')

    parser.add_option('--include-hangs', action='store_true',
                      dest='include_hangs',
                      default=False,
                      help='Include hang signatures. The default is to exclude them.')

    parser.add_option('--start-date', action='store', type='string',
                      dest='start_date', default=None,
                      help='Start date for crashes when loading urls from '
                      'socorro. The default is yesterday.')

    parser.add_option('--stop-date', action='store', type='string',
                      dest='stop_date', default=None,
                      help='Stop date for crashes when loading urls from '
                      'socorro. The default is today.')

    parser.add_option('--username', action='store', type='string',
                      dest='username',
                      default=None,
                      help='Bughunter user name associated with the url '
                      'submission when loading urls from a file.')

    parser.add_option('--email', action='store', type='string',
                      dest='email',
                      default=None,
                      help='Bughunter email associated with the url '
                      'submission when loading urls from a file.')

    parser.add_option('--urls', action='store', type='string',
                      dest='urlsfile',
                      default=None,
                      help='File containing urls to load when loading urls '
                      'from a file.')

    parser.add_option('--duplicates', action='store_true',
                      dest='duplicates',
                      default=False,
                      help='Included duplicates. Default is to exclude them.')

    parser.add_option('--signature', action='store', type='string',
                      dest='signature',
                      default=None,
                      help='Signature to use when loading urls from a  file.')

    (options, args) = parser.parse_args()

    crashloader = CrashLoader()

    if options.skipurlsfile:
        skipurlsfilehandle = open(options.skipurlsfile, 'r')
        for skipurl in skipurlsfilehandle:
            skipurl = skipurl.rstrip('\n')
            crashloader.skipurls.append(skipurl)
        skipurlsfilehandle.close()
    if options.urlsfile:
        if not options.username and not options.email:
            parser.error('username or email is required')
        user_id = utils.get_django_user_id(options.username, options.email)
        if not user_id:
            parser.error('username was not found in bughunter')
    else:
        today = datetime.datetime.now().date()
        if not options.stop_date:
            options.stop_date = today.isoformat()
        if not options.start_date:
            options.start_date = (today - datetime.timedelta(days=1)).isoformat()

    while not utils.getLock('sisyphus.bughunter.sitetestrun', 300):
        continue

    if options.duplicates:
        waiting_testruns = {}
    else:
        waiting_testruns = crashloader.load_waiting_testruns()
    if options.urlsfile:
        urls = []
        urlsfilehandle = open(options.urlsfile, 'r')
        for url in urlsfilehandle:
            url = url.rstrip('\n')[:1000] ### Should get the length from the model
            urls.append(url)
        urlsfilehandle.close()
        pending_socorro = crashloader.load_urls(urls, user_id, options.signature)
        priority = '1'
    else:
        pending_socorro = crashloader.load_socorro_crashdata(options.start_date,
                                                             options.stop_date,
                                                             options.include_hangs)
        priority = '3'
    crashloader.create_socorro_rows(pending_socorro, waiting_testruns, priority)

    try:
        lockDuration = utils.releaseLock('sisyphus.bughunter.sitetestrun')
        print "Total lock time %s" % lockDuration
    except:
        exceptionType, exceptionValue, errorMessage = utils.formatException()
        print '%s, %s' % (exceptionValue, errorMessage)

if __name__ == '__main__':
    main()
