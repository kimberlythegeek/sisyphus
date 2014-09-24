# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

""" build_database.py - maintain a local database of Firefox builds

build_database.py will create a local json database
build_database.json in the user's home directory that contains
information on the Firefox builds created for the Beta, Aurora and
Nightly channels since April 2011.

It is intended to be used either as a standalone program or as a
module.

The primary intended use for the build_database.json file is for use
when searching for fixes or regressions in Firefox by performing
binary searches on the historical Firefox builds.

The json structure of the database is illustrated by:

{
    "builds": {
        "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/2011/04/2011-04-01-03-mozilla-central-debug/firefox-4.2a1pre.en-US.debug-mac.dmg ": {
            "buildid": "20110331213228", 
            "changeset": "http://hg.mozilla.org/mozilla-central/rev/1a89509e25e4"
        }, 
        "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/2011/04/2011-04-01-03-mozilla-central/firefox-4.2a1pre.en-US.mac.dmg ": {
            "buildid": "20110401030438", 
            "changeset": "http://hg.mozilla.org/mozilla-central/rev/1a89509e25e4"
        }, 
        ...
    }, 
    "last_update": "2012-06-05-07-45-25"
}
"""

from optparse import OptionParser
import os
import datetime
import sys
import re
import platform
import httplib2
import BeautifulSoup
try:
    import json
except:
    import simplejson as json

sisyphus_dir     = os.environ["TEST_DIR"]
tempdir          = os.path.join(sisyphus_dir, 'bin')
if tempdir not in sys.path:
    sys.path.append(tempdir)

def parse_datetime(s):
    """convert a string of format CCYY-MM-DD or CCYY-MM-DD-HH-MM-SS
    into a datetime object."""

    re_datetime = re.compile(r'(\d{4})-(\d{1,2})-(\d{1,2})')
    match       = re_datetime.match(s)
    if match:
        date = datetime.datetime(int(match.group(1)),
                                 int(match.group(2)),
                                 int(match.group(3)))
    else:
        re_datetime = re.compile(r'(\d{4})-(\d{1,2})-(\d{1,2})(-(\d{1,2})-(\d{1,2})-(\d{1,2}))?')
        match       = re_datetime.match(s)
        if not match:
            raise Exception('Bad Date: ' + s)
        date = datetime.datetime(int(match.group(1)),
                                 int(match.group(2)),
                                 int(match.group(3)),
                                 int(match.group(5)),
                                 int(match.group(6)),
                                 int(match.group(7)))
    return date


def format_datetime(d):
    """format a datetime object into a string with format CCYY-MM-DD-HH-MM-SS"""
    return d.strftime('%Y-%m-%d-%H-%M-%S')

class PlatformData():
    """collect and encapsulate useful platform information into a
    single object."""
    def __init__(self, options):

        os.chdir(sisyphus_dir)

        uname           = os.uname()
        os_name    = uname[0]
        hostname   = uname[1]
        os_version = uname[2]
        cpu_name   = uname[-1]
        bits       = platform.architecture()[0]

        if bits == "32bit":
            self.cpu_name = "-i686"
        elif bits == "64bit":
            self.cpu_name = "-x86_64"

        if options.processor_type:
            if options.processor_type == 'intel32' or options.processor_type == 'amd32':
                self.cpu_name = '-i686'
            elif options.processor_type == 'intel64' or options.processor_type == 'amd64':
                self.cpu_name = '-x86_64'

        if os_name.find("Linux") != -1:
            self.suffix   = 'tar.bz2'
            self.platform = "linux"
        elif os_name.find("Darwin") != -1:
            self.suffix   = 'dmg'
            self.platform = "mac"
            self.cpu_name = '(64)?'
        elif os_name.find("CYGWIN") != -1:
            self.suffix = '(zip|installer\.exe)'
            if "PROCESSOR_ARCHITEW6432" in os.environ and os.environ["PROCESSOR_ARCHITEW6432"]:
                self.platform = 'win64'
                self.cpu_name = "-x86_64"
            else:
                self.platform = 'win32'
                self.cpu_name = ""

            if options.processor_type:
                if options.processor_type == 'intel32':
                    self.platform = 'win32'
                    self.cpu_name = ''
                elif options.processor_type == 'intel64':
                    self.platform = 'win64'
                    self.cpu_name = 'x86_64'
        else:
            raise Exception("invalid os_name: %s" % (os_name))



def build_database(options):

    platform_data = PlatformData(options)

    database_filename = os.path.join(os.environ['HOME'], 'build_database.json')

    try:
        database_file = open(database_filename, 'rb')
        database = json.load(database_file)
    except Exception, e:
        if isinstance(e, IOError) and e.errno == 2 or isinstance(e, ValueError):
            print 'database not found... creating...'
            database = {
                'last_update' : format_datetime(parse_datetime(options.database_start_date)),
                'builds'      : {}
                }
        else:
            raise

    except Exception, e:
        raise

    re_branches = re.compile(r'mozilla-(aurora|beta|central|inbound)(-debug)?/')
    re_builds   = re.compile(r'firefox.*(\.debug-%s|.%s)?%s\.%s' %
                             (platform_data.platform, platform_data.platform,
                              platform_data.cpu_name,
                              platform_data.suffix))
    httplib = httplib2.Http();
    ftpurl = 'http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly'

    now = datetime.datetime.now()
    yesterday = datetime.datetime(now.year, now.month, now.day) - datetime.timedelta(days=1)
    last_update = parse_datetime(database['last_update'])

    while last_update <= yesterday:

        directory_url = '%s/%04d/%02d/' % (ftpurl, last_update.year, last_update.month)
        directory_resp, directory_content = httplib.request(directory_url, "GET")

        if directory_resp.status == 200:
            directory_soup = BeautifulSoup.BeautifulSoup(directory_content)
            for directory_link in directory_soup.findAll('a'):
                match = re_branches.search(directory_link.get('href'))
                if match:
                    builddir_url = '%s%s' % (directory_url, directory_link.get('href'))
                    builddir_resp, build_content = httplib.request(builddir_url, "GET")
                    if builddir_resp.status == 200:
                        builddir_soup = BeautifulSoup.BeautifulSoup(build_content)
                        for build_link in builddir_soup.findAll('a'):
                            match = re_builds.match(build_link.get('href'))
                            if match:
                                buildurl = "%s%s" % (builddir_url, build_link.get('href'))
                                if buildurl in database['builds']:
                                    continue
                                buildtxturl = re.sub(platform_data.suffix, 'txt', buildurl)
                                buildtxturl_resp, buildtxturl_content = httplib.request(buildtxturl, 'GET')
                                if buildtxturl_resp.status == 200:
                                    buildtxt_lines = buildtxturl_content.split('\n')
                                    database['builds'][buildurl] = {
                                        'buildid' : buildtxt_lines[0],
                                        'changeset' : buildtxt_lines[1]
                                        }
                                    # Not all txt files have
                                    # changesets. If the native txt file
                                    # does not have a changeset, assume
                                    # the win32 txt file will have a
                                    # changeset however.
                                    if not database['builds'][buildurl]['changeset']:
                                        buildtxturl = re.sub(platform_data.platform +
                                                             platform_data.cpu_name,
                                                             'win32', buildtxturl)
                                        buildtxturl_resp, buildtxturl_content = httplib.request(buildtxturl, 'GET')
                                        if buildtxturl_resp.status == 200:
                                            buildtxt_lines = buildtxturl_content.split('\n')
                                            database['builds'][buildurl] = {
                                                'buildid' : buildtxt_lines[0],
                                                'changeset' : buildtxt_lines[1]
                                                }

        year = last_update.year
        month = last_update.month
        if last_update.month < 12:
            month += 1
        else:
            year += 1
            month = 1
        last_update = datetime.datetime(year, month, 1)

    database['last_update'] = format_datetime(now)
    database_file = open(database_filename, 'wb')
    database_file.write(json.dumps(database, sort_keys=True, indent=4))
    database_file.close()

    return database

if __name__ == "__main__":

    usage = '''usage: %prog [options]'''

    parser = OptionParser(usage=usage)

    parser.add_option('--database-start-date', action='store',
                      dest='database_start_date',
                      help='Database starting date. Defaults to 2011-04-01',
                      default='2011-04-01')

    parser.add_option('--build-type', action='store',
                      dest='build_type',
                      help='build type: one of opt, debug. Defaults to debug',
                      default='debug')

    parser.add_option('--processor-type', action='store', type='string',
                       dest='processor_type',
                       help='Override default processor type: intel32, intel64, amd32, amd64',
                       default=None)

    (options, args) = parser.parse_args()

    build_database(options)

