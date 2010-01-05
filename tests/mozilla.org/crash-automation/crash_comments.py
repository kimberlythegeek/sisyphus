import sys
import re
import gzip
import textwrap

def create_crash_doc(line):
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
        return None

    doc = {'signature':signature,
           'url':url,
           'type':'crash',
           'uuid_url':uuid_url,
           'client_crash_date':client_crash_date,
           'date_processed':date_processed,
           'last_crash':last_crash,
           'product':product,
           'version':version,
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
    key = crash_doc['signature'] + crash_doc['version'] + crash_doc['client_crash_date']
    return key

def cmp_crash_docs(ldoc, rdoc):
    lkey = crash_key(ldoc)
    rkey = crash_key(rdoc)

    if lkey < rkey:
        return -1
    if rkey > lkey:
        return +1
    return 0

def load_crashdata(crashlogfile, crashlogversion):
    crashlogfilehandle = gzip.GzipFile(crashlogfile)

    crash_docs = []

    for line in crashlogfilehandle:

        crash_doc = create_crash_doc(line)
        if crash_doc is None:
            continue

        if (crash_doc['version'].find(crashlogversion)) != 0:
            continue

        if crash_doc['user_comments'].find('\\N') == 0:
            continue

        crash_docs.append(crash_doc)

    crashlogfilehandle.close()

    crash_docs.sort(cmp_crash_docs)

    return crash_docs

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise Exception, 'usage: crash_comments.py ffversion crashlog'

    class1          = 'gray'
    class2          = 'white'
    lastsignature   = ''
    crashlogversion = sys.argv[-2]
    crashlogfile    = sys.argv[-1]
    crashlogdate    = crashlogfile[0:8]
    crash_docs      = load_crashdata(crashlogfile, crashlogversion)

    print '<html>'
    print '<head>'
    print '<style type="text/css">td {padding: 1em;} .gray {background-color: #ccc} .white { background-color: #fff}</style>'
    print '<title>Crash Comments for version %s, %s</title>' % (crashlogversion, crashlogdate)
    print '</head>'
    print '<body>'

    print '<h1>Crash Comments for version %s, %s</h1>' % (crashlogversion, crashlogdate)

    print '<table border="1">'
    print '<thead>'
    print '<tr>'
    print '<th>version</th>'
    print '<th>client date crashed</th>'
    print '<th>date processed</th>'
    print '<th>comments</th>'
    print '<th>signature</th>'
    print '</thead>'
    print '<tbody>'

    for crash_doc in crash_docs:
        client_crash_date = crash_doc['client_crash_date']
        date_processed = crash_doc['date_processed']
        signature  = crash_doc['signature']
        paren      = signature.find('(')
        if paren != -1:
            signature = signature[:paren]

        if signature != lastsignature:
            tempclass = class2
            class2    = class1
            class1    = tempclass
            lastsignature = signature

        comments = crash_doc['user_comments']
        comments = comments.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        print '<tr class="%s">' % (class1)
        print '<td>%s</td>' % (crash_doc['version'])
        print '<td><a href="%s">%s-%s-%s<br/>%s:%s</a></td>' % (crash_doc['uuid_url'], client_crash_date[0:4], client_crash_date[4:6], client_crash_date[6:8], client_crash_date[8:10], client_crash_date[10:12])
        print '<td>%s-%s-%s<br/>%s:%s</td>' % (date_processed[0:4], date_processed[4:6], date_processed[6:8], date_processed[8:10], date_processed[10:12])
        print '<td>%s</td>' % ("<br/>".join(textwrap.wrap(comments, 70)))
        print '<td>'
        print ('<a href="http://crash-stats.mozilla.com/query/query?do_query=1&product=Firefox&version=Firefox:%s&query_search=signature&query_type=contains&query=%s">%s</a>' % 
               (crash_doc['version'], signature, "<br/>".join(textwrap.wrap(signature, 70))))

        if crash_doc['bug_list'] != '' and crash_doc['bug_list'] != '\\N':
              print '<br/><br/><a href="https://bugzilla.mozilla.org/buglist.cgi?bugidtype=include;bug_id=%s">bugs %s</a></td>' % (crash_doc['bug_list'], "<br/>".join(textwrap.wrap(crash_doc['bug_list'],70)))
        print '</td>'

        print '</tr>'
    print '</tbody>'
    print '</table>'
    print '</body></html>'
