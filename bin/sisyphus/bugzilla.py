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

# http://code.google.com/p/httplib2/
import httplib2

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json

import signal
import sys
import re
import time
import urllib
import datetime

bzapiurl = 'https://api-dev.bugzilla.mozilla.org/latest/'

def timedHttpRequest_handler(signum, frame):
    print 'timedHttpRequest timeout'
    raise IOError('HttpRequestTimeout')

def timedHttpRequest(url, timeout = 300):
    """
    Attempt to perform an http request. If it does not return within
    timeout seconds, raise an empty response. Retry once after a delay
    of 1 minute if the http request throws an exception.

    usage: resp, content = timedHttpRequest('http://example.com/?yomama', 300)

    """
    for attempt in range(2):
        try:
            signal.signal(signal.SIGALRM, timedHttpRequest_handler)

            http = httplib2.Http()
            signal.alarm(timeout)
            resp, content = http.request(url)
            signal.alarm(0)

        except:
            signal.alarm(0)
            # silently fail.
            #exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            #if exceptionType != IOError and exceptionType != HttpLib2Error:
            #    raise
            resp = {}
            content = '{}'
            time.sleep(60)

    try:
        jcontent = json.loads(content)
    except:
        jcontent = {}

    return resp, jcontent

def ageToDate(age):
    return datetime.datetime.strftime(datetime.datetime.now() - datetime.timedelta(days = age), "%Y-%m-%d")

def searchBugzillaSummary(query, querytype='contains', keywords=None, age=None):
    """
    Search bugzilla using the bugzilla rest api for bugs containing
    the string query in the summary and optionally all of the keywords
    returning the response and content as a json 2-tuple.

    To limit the scope of the query, you can specify the number of days
    since the bug was modified in the age argument.

    usage: resp, content = searchBugzillaSummary('yomama')

    NOTE: Only searches the Client Software and Components classifications.
    """

    url = (bzapiurl +
           "bug?classification=Client%20Software&classification=Components" +
           "&summary_type=" + querytype +
           "&summary=" + urllib.quote(query))

    if keywords is not None:
        url += "&keywords_type=contains_all&keywords=" + urllib.quote(keywords)

    if age is not None:
        url += "&changed_after=" + ageToDate(age)

    resp, content = timedHttpRequest(url)

    return resp, content

def searchBugzillaComments(query, querytype='contains', keywords=None, age=None):
    """
    Search bugzilla using the bugzilla rest api for bugs containing
    the string query in the comments and optionally all of the
    keywords returning the response and content as a json 2-tuple.

    usage: resp, content = searchBugzillaComments('yomama')

    To limit the scope of the query, you can specify the number of days
    since the bug was modified in the age argument.

    NOTE: Only searches the Client Software and Components classifications.
    """
    url = (bzapiurl +
           "bug?classification=Client%20Software&classification=Components" +
           "&comment_type=" + querytype +
           "&comment=" + urllib.quote(query))

    if keywords is not None:
        url += "&keywords_type=contains_all&keywords=" + urllib.quote(keywords)

    if age is not None:
        url += "&changed_after=" + ageToDate(age)

    resp, content = timedHttpRequest(url)

    return resp, content

def searchBugzillaUrls(query, querytype='contains', keywords=None, age=None):
    """
    Search bugzilla using the bugzilla rest api for bugs containing
    the string query in either the url or comments and optionally
    the keywords returning the response and content as a json 2-tuple.

    usage: resp, content = searchBugzillaUrls('yomama')

    To limit the scope of the query, you can specify the number of days
    since the bug was modified in the age argument.

    NOTE: Only searches the Client Software and Components classifications.
    """

    query = urllib.quote(query)
    url   = (bzapiurl +
             "bug?classification=Client%20Software&classification=Components" +
             "&field0-0-0=url&type0-0-0=" + querytype + "&value0-0-0=" + query +
             "&field0-0-1=comment&type0-0-1=" + querytype + "&value0-0-1=" + query)

    if keywords is not None:
        url += "&keywords_type=contains_all&keywords=" + urllib.quote(keywords)

    if age is not None:
        url += "&changed_after=" + ageToDate(age)

    resp, content = timedHttpRequest(url)

    return resp, content

def searchBugzillaText(query, querytype='contains', keywords=None, age=None):
    """
    Search bugzilla using the bugzilla rest api for bugs containing
    the string query in either the summary or comments and optionally
    the keywords returning the response and content as a json 2-tuple.

    usage: resp, content = searchBugzillaText('yomama')

    To limit the scope of the query, you can specify the number of days
    since the bug was modified in the age argument.

    NOTE: Only searches the Client Software and Components classifications.
    """

    query = urllib.quote(query)
    url   = (bzapiurl +
             "bug?classification=Client%20Software&classification=Components" +
             "&field0-0-0=summary&type0-0-0=" + querytype + "&value0-0-0=" + query +
             "&field0-0-1=comment&type0-0-1=" + querytype + "&value0-0-1=" + query)

    if keywords is not None:
        url += "&keywords_type=contains_all&keywords=" + urllib.quote(keywords)

    if age is not None:
        url += "&changed_after=" + ageToDate(age)

    resp, content = timedHttpRequest(url)

    return resp, content

def searchBugzillaTextAttachments(query, querytype='contains', keywords=None, age=None):
    """
    Search bugzilla using the bugzilla rest api matching the keywords
    and the string query in text attachments the response and content
    as a json 2-tuple.

    The keywords are absolutely necessary as bugzilla will timeout
    without limiting the query. Therefore the function raises an error
    should keywords not be specified.

    To limit the scope of the query, you can specify the number of days
    since the bug was modified in the age argument.

    usage: resp, content = searchBugzillaTextAttachments('yomama','contains','crash')

    NOTE: Only searches the Client Software and Components classifications.
    """

    if keywords == None:
        raise Exception('searchBugzillaTextAttachmentsKeywords')

    query    = urllib.quote(query)
    keywords = urllib.quote(keywords)

    url   = (bzapiurl +
             "bug?classification=Client%20Software&classification=Components" +
             "&keywords_type=contains_all&keywords=" + keywords +
             "&field0-0-0=attachment.content_type&type0-0-0=contains&value0-0-0=text" +
             "&field0-1-0=attachment.data&type0-1-0=" + querytype + "&value0-1-0=" + query)

    if age is not None:
        url += "&changed_after=" + ageToDate(age)

    resp, content = timedHttpRequest(url)

    return resp, content

if __name__ == "__main__":
    """
    Tests which run when the script is executed rather than imported.
    Usage: python bugzilla.py
    """
    def dump_content(resp, content):
        print "resp: %s" % json.dumps(resp)
        if 'bugs' not in content:
            print "content: %s" % json.dumps(content)
        else:
            bug_list = [bug['id'] for bug in content['bugs']]
            print "bugs: %s" % bug_list

    print "searchBugzillaSummary"
    resp, content = searchBugzillaSummary("Wrong scope, this is really bad!: 'JS_GetGlobalForObject(cx, obj) == newScope'")
    dump_content(resp, content)

    print "searchBugzillaComments"
    resp, content = searchBugzillaComments("Wrong scope, this is really bad!: 'JS_GetGlobalForObject(cx, obj) == newScope'")
    dump_content(resp, content)

    print "searchBugzillaText"
    resp, content = searchBugzillaText("Wrong scope, this is really bad!: 'JS_GetGlobalForObject(cx, obj) == newScope'")
    dump_content(resp, content)

    print "searchBugzillaTextAttachments"
    resp, content = searchBugzillaTextAttachments("qcms_transform_data_rgba qcms_transform_data row_callback MOZ_PNG_push_have_row MOZ_PNG_push_proc_row", "contains_all", "crash")
    dump_content(resp, content)

    print "searchBugzillaComments"
    resp, content = searchBugzillaComments("crash", "contains_all", None, 7)
    dump_content(resp, content)

    print "searchBugzillaUrls"
    resp, content = searchBugzillaUrls("http://test.bclary.com/tests/mozilla.org/js/")
    dump_content(resp, content)
