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
# bug xxx couchquery requires the document ids to be encoded.
# use urllib.quote(...) to encode them.
import couchquery

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json

import urlparse

rePrivateNetworks = re.compile(r'https?://(localhost|127\.0\.0\.1|192\.168\.[0-9]+\.[0-9]+|172\.16\.[0-9]+\.[0-9]+|10\.[0-9]+\.[0-9]+\.[0-9]+)')

supported_versions_hash = None
supported_versions = None
bad_lines = []
bad_results = []
skipurls = []


def create_crash_doc(line, supported_versions_hash):
    global bad_lines

    try:
        # split the line into 16 variables. This will allow comments with
        # embedded tabs to be properly parsed.
        (signature,
         url,
         uuid_url,
         client_crash_date,
         date_processed,
         last_crash,
         product,
         version,
         build,
         branch,
         os_name,
         os_version,
         cpu_name,
         address,
         bug_list,
         user_comments,) = line.split('\t', 15)
    except:
        bad_lines.append(line)
        output('e')
        print 'create_crash_doc: bad line'
        return None

    if url.find('http') != 0:
        return None # skip non-http urls

    match = rePrivateNetworks.match(url)
    if match:
        return None # skip private networks

    try:
        urlParseResult = urlparse.urlparse(url)
        if urlParseResult.port:
            return None # skip non default ports
    except:
        # catch malformed url errors
        return None

    for skipurl in skipurls:
        if re.search(skipurl, url):
            return None

    minor_version = ordered_ffversion(version)
    major_version = minor_version[0:4]

    if not major_version in supported_versions_hash:
        return None # skip unsupported major versions

    if version.find('4.0') == 0 and build < '20100101':
        return None # Ignore bogus version 4

    doc = {'signature':signature,
           'url':url,
           'type':'crash',
           'uuid_url':uuid_url,
           'client_crash_date':client_crash_date,
           'date_processed':date_processed,
           'last_crash':last_crash,
           'product':product,
           'version':version,
           'major_version':major_version,
           'minor_version':minor_version,
           'build':build,
           'branch':branch,
           'os_name':os_name,
           'os_version':os_version,
           'cpu_name':cpu_name,
           'address':address,
           'bug_list':bug_list,
           'user_comments':user_comments}

    return doc

def crash_key(crash_doc):
    key = (crash_doc['signature'] + ':' + crash_doc['major_version'] + ':' + crash_doc['os_name'] + ':' + 
           crash_doc['cpu_name'] + ':' + '.'.join(crash_doc['os_version'].split('.')[0:2]))
    return key

def cmp_crash_docs(ldoc, rdoc):
    lkey = crash_key(ldoc)
    rkey = crash_key(rdoc)

    if lkey < rkey:
        return -1
    if rkey > lkey:
        return +1
    return 0

def create_signature_doc(crashlogdate, crash_doc):
    minor_version                   = crash_doc['minor_version']
    major_version                   = crash_doc['major_version']

    signature_doc                   = {}
    signature_doc['_id']            = re.sub(r'[^a-zA-Z0-9_]', '_', crashlogdate + ':' + crash_key(crash_doc))
    signature_doc['type']           = 'signature'
    signature_doc['date']           = crashlogdate
    signature_doc['signature']      = crash_doc['signature']
    # signature_doc['address']      = crash_doc['address']
    signature_doc['versionhash']    = {crash_doc['version'] : 1}
    signature_doc['major_version']  = major_version
    signature_doc['major_versionhash'] = {major_version: {minor_version: 1}}
    signature_doc['os_name']        = crash_doc['os_name']
    signature_doc['os_version']     = '.'.join(crash_doc['os_version'].split('.')[0:2])
    signature_doc['os_versionhash'] = {crash_doc['os_version']: 1}
    signature_doc['cpu_name']       = crash_doc['cpu_name']
    # each crash report with the same signature is guaranteed to contain the
    # same list of bugs.
    signature_doc['bug_list']       = crash_doc['bug_list']
    signature_doc['urlhash']        = {crash_doc['url']: 1}
    signature_doc['worker']         = None
    signature_doc['processed_by']   = {}
    signature_doc['priority']       = '1'  # default priority. priority 0 will be processed first.

    return signature_doc

def output(s):
    sys.stdout.write(s)
    sys.stdout.flush()

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


def process_crashdata(db, crashlogdate, crash_docs, ffversionshash, supported_versions_hash, supported_versions):
    global bad_results

    next_signature_key = None
    doc_buffer = []
    count = 0

    crash_doc = crash_docs.pop(0)
    curr_signature_key = crash_key(crash_doc)
    curr_signature_doc = create_signature_doc(crashlogdate, crash_doc)

    for crash_doc in crash_docs:

        next_signature_key = crash_key(crash_doc)

        if next_signature_key < curr_signature_key:
            raise Exception('input file out of order: curr_signature_key: %s, next_signature_key: %s' % (curr_signature_key, next_signature_key))

        if curr_signature_key == next_signature_key:
            if not crash_doc['url'] in curr_signature_doc['urlhash']:
                curr_signature_doc['urlhash'][crash_doc['url']] = 0
            curr_signature_doc['urlhash'][crash_doc['url']] += 1

            if not crash_doc['os_version'] in curr_signature_doc['os_versionhash']:
                curr_signature_doc['os_versionhash'][crash_doc['os_version']] = 0
            curr_signature_doc['os_versionhash'][crash_doc['os_version']] += 1

            version = crash_doc['version']
            if not version in curr_signature_doc['versionhash']:
                curr_signature_doc['versionhash'][version] = 0
            curr_signature_doc['versionhash'][version] += 1

            minor_version = crash_doc['minor_version']
            major_version = crash_doc['major_version']
            if not major_version in curr_signature_doc['major_versionhash']:
                curr_signature_doc['major_versionhash'][major_version] = {}
            if not minor_version in curr_signature_doc['major_versionhash'][major_version]:
                curr_signature_doc['major_versionhash'][major_version][minor_version] = 0

            curr_signature_doc['major_versionhash'][major_version][minor_version] += 1
        else:
            skipsignature = finalize_curr_signature_doc(curr_signature_doc, ffversionshash, supported_versions)

            if not skipsignature:
                curr_signature_doc.pop('urlhash')
                doc_buffer.append(curr_signature_doc)
                if len(doc_buffer) == 5:  # make configurable
                    info = db.create(doc_buffer)
                    for result in info:
                        if 'error' in result:
                            print 'db.create error %s' % (result)
                            bad_results.append(result)
                            output('x')
                    count += 5 # make configurable
                    output('.')
                    doc_buffer = []
            curr_signature_doc = create_signature_doc(crashlogdate, crash_doc)
            curr_signature_key = next_signature_key

    skipsignature = finalize_curr_signature_doc(curr_signature_doc, ffversionshash, supported_versions)

    if not skipsignature:
        curr_signature_doc.pop('urlhash')
        doc_buffer.append(curr_signature_doc)

    info = db.create(doc_buffer)
    for result in info:
        if 'error' in result:
            print 'db.create error %s' % (result)
            bad_results.append(result)
            output('x')
    count += len(doc_buffer)
    output('.')
    doc_buffer = []

    print ''
    print 'Created '+str(count)+' Documents'
    if len(bad_lines) > 0:
        print 'Failed to parse %d lines' % (len(bad_lines))
        for line in bad_lines:
            print line
    if len(bad_results) > 0:
        print 'Failed to create %d Documents' % (len(bad_results))
        for result in bad_results:
            print result

def finalize_curr_signature_doc(curr_signature_doc, ffversionshash, supported_versions):
    skipsignature = False
    curr_signature_doc['urls'] = [url for url in curr_signature_doc['urlhash']]

    # get signature's maximum major_version
    sig_major_versions = [sig_major_version for sig_major_version in curr_signature_doc['major_versionhash']]
    sig_major_versions.sort()
    sig_major_version = sig_major_versions[-1]

    if sig_major_version < supported_versions[0]:
        # skip if the signature's maximum version is less than our minimum version
        skipsignature = True
    else:
        # cut off global minor version is two releases prior to this major version
        glb_minor_versions = [ glb_minor_version for glb_minor_version in ffversionshash[sig_major_version] ]
        if len(glb_minor_versions) < 3:
            glb_minor_version = '000000'
        else:
            glb_minor_versions.sort()
            glb_minor_version  = glb_minor_versions[-3]

        # get signature's maximum minor_version
        sig_minor_versions = [sig_minor_version for sig_minor_version in curr_signature_doc['major_versionhash'][sig_major_version]]
        sig_minor_versions.sort()
        sig_minor_version = sig_minor_versions[-1]

        if sig_minor_version < glb_minor_version:
            skipsignature = True

    return skipsignature


def load_crashdata(crashlogfile, crash_docs, ffversionshash, supported_versions_hash):
    crashlogfilehandle = gzip.GzipFile(crashlogfile)

    for line in crashlogfilehandle:
        crash_doc = create_crash_doc(line, supported_versions_hash)
        if crash_doc is None:
            continue

        # collect global versions
        minor_version = crash_doc['minor_version']

        major_version = minor_version[:4]
        if not major_version in ffversionshash:
            ffversionshash[major_version] = {}
        if not minor_version in ffversionshash[major_version]:
            ffversionshash[major_version][minor_version] = 0
        ffversionshash[major_version][minor_version] += 1

        crash_docs.append(crash_doc)

    crashlogfilehandle.close()

    crash_docs.sort(cmp_crash_docs)

def main():
    global supported_versions_hash, supported_versions

    usage = '''usage: %prog [options] crashdump

Example:
%prog --couch http://couchserver 20091128-crashdata.csv.gz
'''
    parser = OptionParser(usage=usage)
    parser.add_option('--couch', action='store', type='string',
                      dest='couchserveruri',
                      default='http://127.0.0.1:5984',
                      help='uri to couchdb server')
    parser.add_option('-s', '--skipurls', action='store', type='string',
                      dest='skipurlsfile',
                      default=None,
                      help='file containing url patterns to skip when uploading.')
    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.error('crashdump file is required.')

    crashlogfile = args[0]
    crashlogdate = os.path.basename(crashlogfile)[0:8]

    crashtestdb = couchquery.Database(options.couchserveruri + '/crashtest')
    buildsdb    = couchquery.Database(options.couchserveruri + '/builds')

    try:
        # attempt to create the database
        couchquery.createdb(crashtestdb)
        couchquery.deletedb(crashtestdb)
        raise Exception('The crashtest database does not exist. It must be created via crashtest.py')

    except Exception, ex:
        # assume error is due to already existing db
        pass

    if options.skipurlsfile:
        skipurlsfilehandle = open(options.skipurlsfile, 'r')
        for skipurl in skipurlsfilehandle:
            skipurl = skipurl.rstrip('\n')
            skipurls.append(skipurl)

    branches_doc = buildsdb.get('branches')

    if branches_doc is None:
        raise Exception("crashtest requires the branches document in the builds database.")

    supported_versions = list(branches_doc["major_versions"])
    supported_versions.sort()
    supported_versions_hash = {}
    for supported_version in supported_versions:
        supported_versions_hash[supported_version] = 1

    crash_docs = []
    ffversionshash = {}
    load_crashdata(crashlogfile, crash_docs, ffversionshash, supported_versions_hash)

    print '__main__: crashlogdate: %s, total docs: %d, supported_versions: %s, ffversionshash: %s' % (crashlogdate, len(crash_docs), supported_versions, ffversionshash)
    process_crashdata(crashtestdb, crashlogdate, crash_docs, ffversionshash, supported_versions_hash, supported_versions)

if __name__ == '__main__':
    main()
