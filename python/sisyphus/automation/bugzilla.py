# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

# http://code.google.com/p/httplib2/
import httplib2

import datetime
import json
import re
import signal
import sys
import time
import urllib

bzapiurl = 'https://api-dev.bugzilla.mozilla.org/latest/'

def timedHttpRequest_handler(signum, frame):
    print 'timedHttpRequest timeout'
    raise IOError('HttpRequestTimeout')

def timedHttpRequest(url, attempts = 1, timeout = 300):
    """
    Attempt to perform an http request. If it does not return within
    timeout seconds, raise an empty response. Retry once after a delay
    of 1 minute if the http request throws an exception.

    usage: resp, content = timedHttpRequest('http://example.com/?yomama', 300)

    """
    for attempt in range(attempts):
        try:
            signal.signal(signal.SIGALRM, timedHttpRequest_handler)

            http = httplib2.Http()
            signal.alarm(timeout)
            resp, content = http.request(url)
            signal.alarm(0)

        except KeyboardInterrupt, SystemExit:
            raise
        except:
            signal.alarm(0)
            # silently fail.
            #exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            #if exceptionType != IOError and exceptionType != HttpLib2Error:
            #    raise
            resp = {}
            content = '{}'

    try:
        jcontent = json.loads(content)
    except KeyboardInterrupt, SystemExit:
        raise
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

    # If age is not specified, default to one year to prevent queries from hitting
    # the entire history.
    if age is None:
        age = 365

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

    # If age is not specified, default to one year to prevent queries from hitting
    # the entire history.
    if age is None:
        age = 365

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

    # If age is not specified, default to one year to prevent queries from hitting
    # the entire history.
    if age is None:
        age = 365

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

    # If age is not specified, default to one year to prevent queries from hitting
    # the entire history.
    if age is None:
        age = 365

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

    # If age is not specified, default to one year to prevent queries from hitting
    # the entire history.
    if age is None:
        age = 365

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
