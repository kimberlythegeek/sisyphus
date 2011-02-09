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
import urllib
# bug xxx couchquery requires the document ids to be encoded.
# use urllib.quote(...) to encode them.
import couchquery

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json

import urlparse

def main():

    usage = '''usage: %prog [options] --urls urls.list

Example:
%prog --couch http://couchserver --urls urls.list
'''
    parser = OptionParser(usage=usage)

    parser.add_option('--couch', action='store', type='string',
                      dest='couchserveruri',
                      default='http://127.0.0.1:5984',
                      help='uri to couchdb server')

    parser.add_option('--database', action='store', type='string',
                      dest='databasename',
                      help='name of database, defaults to sisyphus.',
                      default='sisyphus')

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

    testdb = couchquery.Database(options.couchserveruri + '/' + options.databasename)

    skipurls = []
    if options.skipurlsfile:
        skipurlsfilehandle = open(options.skipurlsfile, 'r')
        for skipurl in skipurlsfilehandle:
            skipurl = skipurl.rstrip('\n')
            skipurls.append(skipurl)
        skipurlsfilehandle.close()

    branches_doc = testdb.get('branches')
    if branches_doc is None:
        raise Exception("crashtest requires the branches document in the builds database.")

    operating_systems = {}

    matching_worker_rows  = testdb.views.crashtest.matching_workers()

    if len(matching_worker_rows) == 0:
        print "There are no workers to use to determine operating systems for the jobs"
        exit(1)

    matching_worker_keys = matching_worker_rows.keys()

    for worker_key in matching_worker_keys:
        os_name    = worker_key[0]
        os_version = worker_key[1]
        cpu_name   = worker_key[2]

        if os_name not in operating_systems:
            operating_systems[os_name] = {}

        if os_version not in operating_systems[os_name]:
            operating_systems[os_name][os_version] = {}

        if cpu_name not in operating_systems[os_name][os_version]:
            operating_systems[os_name][os_version][cpu_name] = 1

    rePrivateNetworks = re.compile(r'https?://(localhost|127\.0\.0\.1|192\.168\.[0-9]+\.[0-9]+|172\.16\.[0-9]+\.[0-9]+|10\.[0-9]+\.[0-9]+\.[0-9]+)')

    urlsfilehandle = open(options.urlsfile, 'r')
    for url in urlsfilehandle:
        url = url.rstrip('\n')
        if url.find('http') != 0:
            return None # skip non-http urls

        match = rePrivateNetworks.match(url)
        if match:
            continue # skip private networks

        try:
            urlParseResult = urlparse.urlparse(url)
            if urlParseResult.port:
                continue # skip non default ports
        except:
            # catch malformed url errors
            continue

        for skipurl in skipurls:
            if re.search(skipurl, url):
                continue

        for major_version in branches_doc["version_to_branch"]:
            minor_version = major_version

            for os_name in operating_systems:
                for os_version in operating_systems[os_name]:
                    for cpu_name in operating_systems[os_name][os_version]:

                        # PowerPC is not supported after Firefox 3.6
                        if major_version > '0306' and cpu_name == 'ppc':
                            continue

                        signature_doc                   = {}
                        signature_doc['type']           = 'signature'
                        signature_doc['major_version']  = major_version
                        signature_doc['os_name']        = os_name
                        signature_doc['os_version']     = os_version
                        signature_doc['cpu_name']       = cpu_name
                        signature_doc['urls']           = [url]
                        signature_doc['date']           = None
                        signature_doc['signature']      = options.signature
                        signature_doc['bug_list']       = None
                        signature_doc['worker']         = None
                        signature_doc['processed_by']   = {}
                        signature_doc['priority']       = '1'  # priority 0 will be processed first.
                        try:
                            testdb.create(signature_doc)
                        except Exception, e:
                            print "Exception %s creating signature %s" % (e.message, signature_doc)

    urlsfilehandle.close()

if __name__ == '__main__':
    main()
