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
import gzip
import urllib

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json

import urlparse

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

rePrivateNetworks = re.compile(r'https?://(localhost|127\.0\.0\.1|192\.168\.[0-9]+\.[0-9]+|172\.16\.[0-9]+\.[0-9]+|10\.[0-9]+\.[0-9]+\.[0-9]+)')

options              = None
skipurls             = []
supported_products   = {}
supported_versions   = {}
supported_branches   = {}
supported_buildtypes = {}
operating_systems    = {}

def load_supported_products():
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
    branches_rows = models.Branch.objects.all()

    if len(branches_rows) == 0:
        raise Exception('Branch table is empty.')

    for branch_row in branches_rows:
        product = branch_row.product
        supported_products[product] = 1
        if product not in supported_buildtypes:
            supported_buildtypes[product] = {}
        if product not in supported_versions:
            supported_versions[product] = {}
        if product not in supported_branches:
            supported_branches[product] = {}
        supported_buildtypes[product][branch_row.buildtype] = 1
        supported_versions[product][branch_row.major_version] = branch_row.branch
        if branch_row.branch not in supported_branches[product]:
            supported_branches[product][branch_row.branch] = branch_row.major_version
        elif branch_row.major_version > supported_branches[product][branch_row.branch]:
            supported_branches[product][branch_row.branch] = branch_row.major_version

def load_operating_systems():
    matching_worker_rows  = models.Worker.objects.filter(worker_type__exact = 'crashtest')

    if len(matching_worker_rows) == 0:
        raise Exception("There are no workers to use to determine operating systems for the jobs")

    for worker_row in matching_worker_rows:
        if worker_row.state == 'disabled' or worker_row.state == 'zombie':
            continue

        os_name    = worker_row.os_name
        os_version = worker_row.os_version
        cpu_name   = worker_row.cpu_name

        if os_name not in operating_systems:
            operating_systems[os_name] = {}

        if os_version not in operating_systems[os_name]:
            operating_systems[os_name][os_version] = {}

        if cpu_name not in operating_systems[os_name][os_version]:
            operating_systems[os_name][os_version][cpu_name] = 1


def ordered_ffversion(versionstring):
     versionstring = re.sub('[a-z].*$', '', versionstring)
     version = ''
     versionparts = re.split('[.]*', versionstring)
     for i in range(0,len(versionparts)):
         try:
             version += ( '00' +  versionparts[i] )[-2:]
         except:
             break # ignore and terminate

     return version


def load_waiting_testruns():

    waiting_testruns = {}

    cursor = connection.cursor()
    if cursor.execute("SELECT SocorroRecord.url, " +
                      "SiteTestRun.os_name, " +
                      "SiteTestRun.os_version, " +
                      "SiteTestRun.cpu_name, " +
                      "SiteTestRun.branch, " +
                      "SiteTestRun.product, " +
                      "SiteTestRun.buildtype " +
                      "FROM SocorroRecord, SiteTestRun WHERE " +
                      "SiteTestRun.socorro_id = SocorroRecord.id AND " +
                      "SiteTestRun.state = 'waiting'"):
        row = cursor.fetchone()
        while row is not None:
            key = "%s:%s:%s:%s:%s:%s:%s" % (
                row[0], # url
                row[1], # os_name
                row[2], # os_version
                row[3], # cpu_name
                row[4], # branch
                row[5], # product
                row[6], # buildtype
                )

            waiting_testruns[key] = 1
            row = cursor.fetchone()

    return waiting_testruns

def load_crashdata(crashlogfile):

    pending_socorro = {}

    crashlogfilehandle = gzip.GzipFile(crashlogfile)

    # read the first line to get the field names and
    # create a list|dictionary to map field values to names.
    line       = crashlogfilehandle.readline().strip()
    field_list = line.split('\t')
    fields     = {}
    for field in field_list:
        fields[field] = None

    def get_field(name):
        try:
            field = fields[name]
            if field is not None:
                field = field.strip()
            return field
        except KeyError:
            return None

    def dump_fields():
        for field in field_list:
            print "%s = %s" % (field, fields[field])

    for line in crashlogfilehandle:

        line = line.strip()

        values = line.split('\t')

        for ifield in range(len(values)):
            try:
                fields[field_list[ifield]] = values[ifield]
            except IndexError:
                #print "IndexError: ifield = %d, len(field_list) = %d, len(values) = %d, field_list=%s, values=%s" % (ifield, len(field_list), len(values), field_list, values)
                # assume last field has extra tabs and append to it.
                fields[field_list[-1]] += '\t' + values[ifield]

        signature         = get_field('signature')
        url               = get_field('url')
        uuid              = get_field('uuid_url')
        client_crash_date = get_field('client_crash_date')
        date_processed    = get_field('date_processed')
        last_crash        = get_field('last_crash')
        product           = get_field('product')
        version           = get_field('version')
        build             = get_field('build')
        branch            = get_field('branch')
        os_name           = get_field('os_name')
        os_version        = get_field('os_version')
        os_full_version   = os_version
        cpu_info          = get_field('cpu_info')
        address           = get_field('address')
        bug_list          = get_field('bug_list')
        user_comments     = get_field('user_comments')
        uptime_seconds    = get_field('uptime_seconds')
        email             = get_field('email')
        adu_count         = get_field('adu_count')
        topmost_filenames = get_field('topmost_filenames')
        addons_checked    = get_field('addons_checked')
        flash_version     = get_field('flash_version')
        hangid            = get_field('hangid').split(' ')[0] # handle occasional hangid ~ uuid | -------
        reason            = get_field('reason')
        process_type      = get_field('process_type')
        app_notes         = get_field('app_notes')
        # new field not in db
        install_age       = get_field('install_age')

        # Firefox -> firefox
        product    = product.lower()

        # fennec -> firefox
        if product not in supported_products:
            product = 'firefox'

        # 6.1.7601 Service Pack 1 -> 6.1
        os_version = '.'.join(os_full_version.split('.')[0:2])

        if url.find('http') != 0:
            continue # skip non-http urls

        match = rePrivateNetworks.match(url)
        if match:
            continue # skip private networks

        if signature.find('hang ') == 0:
            # ignore hang signatures since their urls are duplicate in the matched crash signature.
            continue

        try:
            url = utils.encodeUrl(url)
        except Exception, e:
            exceptionType, exceptionValue, errorMessage = utils.formatException()
            print '%s, %s: url: %s' % (exceptionValue, errorMessage, url)
            continue

        skipit = False
        for skipurl in skipurls:
            if re.search(skipurl, url):
                skipit = True
                break

        if skipit:
            continue

        minor_version = ordered_ffversion(version)
        major_version = minor_version[0:4]

        if not major_version in supported_versions[product]:
            continue # skip unsupported major versions

        if version.find('4.0') == 0 and build < '20100101':
            continue # Ignore bogus version 4

        # The branch data from socorro is unreliable as it depends
        # on data entry which is notoriously wrong. However the
        # version number is guaranteed to be correct. Create the branch
        # information from the Branch table.
        branch = supported_versions[product][major_version]

        # remove trailing | processor family data
        match = re.match(r'([^| ]*).*', cpu_info)
        if match:
            cpu_name = match.group(1)

        socorro_row = models.SocorroRecord(
            signature               = utils.crash_report_field2string(signature),
            url                     = url,
            uuid                    = utils.crash_report_field2string(uuid, 'http://crash-stats.mozilla.com/report/index/'),
            client_crash_date       = client_crash_date,
            date_processed          = date_processed,
            last_crash              = utils.crash_report_field2int(last_crash),
            product                 = product,
            version                 = version,
            build                   = build,
            branch                  = branch,
            os_name                 = utils.crash_report_field2string(os_name),
            os_full_version         = utils.crash_report_field2string(os_full_version),
            os_version              = utils.crash_report_field2string(os_version),
            cpu_info                = utils.crash_report_field2string(cpu_info),
            cpu_name                = utils.crash_report_field2string(cpu_name),
            address                 = utils.crash_report_field2string(address),
            bug_list                = utils.crash_report_field2string(bug_list),
            user_comments           = utils.crash_report_field2string(unicode(user_comments, errors='ignore')),
            uptime_seconds          = utils.crash_report_field2int(uptime_seconds),
            adu_count               = utils.crash_report_field2int(adu_count),
            topmost_filenames       = utils.crash_report_field2string(topmost_filenames),
            addons_checked          = utils.crash_report_field2string(addons_checked),
            flash_version           = utils.crash_report_field2string(flash_version),
            hangid                  = utils.crash_report_field2string(hangid),
            reason                  = utils.crash_report_field2string(reason),
            process_type            = utils.crash_report_field2string(process_type),
            app_notes               = utils.crash_report_field2string(unicode(app_notes, errors='ignore')),
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

    crashlogfilehandle.close()

    return pending_socorro

def create_socorro_rows(pending_socorro, waiting_testruns):

    keys = [key for key in pending_socorro]

    for key in keys:

        socorro_row = pending_socorro[key]

        del pending_socorro[key]

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
        major_version = supported_branches[product][branch]

        sitetestrun_operating_systems = {}
        if os_name in operating_systems:
            if os_version in operating_systems[os_name]:
                sitetestrun_operating_systems[os_name] = {}
                sitetestrun_operating_systems[os_name][os_version] = {}
                if cpu_name in operating_systems[os_name][os_version]:
                    # We have an exact match, create a single job for the operating system,
                    # version and cpu.
                    sitetestrun_operating_systems[os_name][os_version] = {cpu_name : 1}
                else:
                    # We have a match on the operating system and version but not the cpu,
                    # create jobs for this operating system and version and for each
                    # available cpu
                    sitetestrun_operating_systems[os_name][os_version] = dict(operating_systems[os_name][os_version])
            else:
                # We have a match on the operating system but not the version,
                # create jobs for this operating system and for each of the available
                # versions and cpus
                sitetestrun_operating_systems[os_name] = dict(operating_systems[os_name])
        else:
            # We do not have a match on the operating system,
            # create jobs for each of the available operating systems, versions and cpus
            sitetestrun_operating_systems = dict(operating_systems)

        # Only save the SocorroRecord if the corresponding SiteTestRun
        # is saved. Therefore wait until we save the SiteTestRun to
        # save the SocorroRow.
        socorro_row_saved = False

        for sitetestrun_os_name in sitetestrun_operating_systems:
            for sitetestrun_os_version in sitetestrun_operating_systems[sitetestrun_os_name]:
                for sitetestrun_cpu_name in sitetestrun_operating_systems[sitetestrun_os_name][sitetestrun_os_version]:
                    for buildtype in supported_buildtypes[product]:

                        sitetestrun_key = "%s:%s:%s:%s:%s:%s:%s" % (
                            socorro_row.url,
                            sitetestrun_os_name,
                            sitetestrun_os_version,
                            sitetestrun_cpu_name,
                            branch,
                            product,
                            buildtype
                            )

                        if sitetestrun_key in waiting_testruns:
                            continue

                        try:
                            if not socorro_row_saved:
                                socorro_row.save()
                                socorro_row_saved = True

                            test_run = models.SiteTestRun(
                                os_name           = sitetestrun_os_name,
                                os_version        = sitetestrun_os_version,
                                cpu_name          = sitetestrun_cpu_name,
                                product           = product,
                                branch            = branch,
                                buildtype         = buildtype,
                                build_cpu_name    = None,
                                worker            = None,
                                socorro           = socorro_row,
                                changeset         = None,
                                datetime          = utils.getTimestamp(),
                                major_version     = major_version,
                                bug_list          = None,
                                crashed           = False,
                                extra_test_args   = None,
                                steps             = '',
                                fatal_message     = None,
                                exitstatus        = None,
                                log               = None,
                                priority          = '3',
                                state             = 'waiting',
                                )
                            try:
                                test_run.save()
                                waiting_testruns[sitetestrun_key] = 1
                            except Exception, e:
                                print "%s saving SiteTestRun: %s, %s : %s : %s : %s : %s" % (
                                    e,
                                    socorro_row.url,
                                    test_run.os_name,
                                    test_run.os_version,
                                    test_run.cpu_name,
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

    usage = '''usage: %prog [options] crashdump

Example:
%prog 20091128-crashdata.csv.gz
'''
    parser = OptionParser(usage=usage)

    parser.add_option('--skipurls', action='store', type='string',
                      dest='skipurlsfile',
                      default=None,
                      help='file containing url patterns to skip when uploading.')

    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.error('crashdump file is required.')

    crashlogfile = args[0]
    crashlogdate = os.path.basename(crashlogfile)[0:8]

    if options.skipurlsfile:
        skipurlsfilehandle = open(options.skipurlsfile, 'r')
        for skipurl in skipurlsfilehandle:
            skipurl = skipurl.rstrip('\n')
            skipurls.append(skipurl)
        skipurlsfilehandle.close()

    load_supported_products()
    load_operating_systems()
    waiting_testruns = load_waiting_testruns()
    pending_socorro = load_crashdata(crashlogfile)
    create_socorro_rows(pending_socorro, waiting_testruns)

if __name__ == '__main__':
    main()
