import os
import sys
import re
import datetime
import simplejson

from collections import defaultdict

from django.contrib.auth import authenticate, login, logout
from django.db import connection, transaction
from django.db.models import Model
from django.core import serializers
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect, HttpResponseServerError, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token

from django.conf import settings

from django.utils.encoding import iri_to_uri, smart_str, smart_unicode, force_unicode
from django.utils.http import urlquote
import urllib

from sisyphus.webapp.bughunter import models
from sisyphus.webapp import settings
from sisyphus.automation import utils

APP_JS = 'application/json'

#######
#Uncomment the following lines to redirect stdout to a log file for debugging
######
#saveout = sys.stdout
#log_out = open('/var/log/django/sisyphus.error.log', 'w')
#sys.stdout = log_out

def doParseDate(datestring):
    """Given a date string, try to parse it as an ISO 8601 date.
    If that fails, try parsing it with the parsedatetime module,
    which can handle relative dates in natural language."""
    datestring = datestring.strip()
    # This is sort of awful. Match YYYY-MM-DD hh:mm:ss, with the time parts all being optional
    m = re.match("^(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)(?: (?P<hour>\d\d)(?::(?P<minute>\d\d)(?::(?P<second>\d\d))?)?)?$", datestring)
    if m:
        date = (int(m.group("year")), int(m.group("month")), int(m.group("day")),
                m.group("hour") and int(m.group("hour")) or 0,
                m.group("minute") and int(m.group("minute")) or 0,
                m.group("second") and int(m.group("second")) or 0,
                0, # weekday
                0, # yearday
                -1) # isdst
    else:
        # fall back to parsedatetime
        date, x = cal.parse(datestring)
    return time.mktime(date)

def login_required(func):
    def wrap(request, *a, **kw):
        if not request.user.is_authenticated():
            #######
            #If it's an HTML page redirect to login
            #######
            if func.__name__ in VIEW_PAGES:
               return HttpResponseRedirect(settings.VIEW_LOGIN_PAGE)
            else:
               return HttpResponseForbidden()
        return func(request, *a, **kw)
    return wrap


@csrf_exempt
def log_in(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    post = simplejson.loads(request.raw_post_data)
    username = post['username']
    password = post['password']
    user = authenticate(username=username, password=password)
    if not user or not user.is_active:
        response = {}
    else:
        login(request, user)
        response = {'username': user.username}
    json = simplejson.dumps(response)
    return HttpResponse(json, mimetype=APP_JS)

def log_out(request):
    logout(request)
    return HttpResponse('{}', mimetype=APP_JS)


def crashtests(request):
    return render_to_response('bughunter.crashtests.html', {})

def unittests(request):
    return render_to_response('bughunter.unittests.html', {})

def home(request):
    return render_to_response('bughunter.index.html', {})

@login_required
def worker_summary(request):

    worker_types = ['builder', 'crashtest', 'unittest']
    worker_data  = {}

    worker_rows = models.Worker.objects.all()

    for worker_row in worker_rows:
        worker_key  = worker_row.os_name + ' ' + worker_row.os_version + ' ' + worker_row.cpu_name

        if worker_key not in worker_data:
            worker_data[worker_key] = {}
            for worker_type in worker_types:
                worker_data[worker_key][worker_type] = {"active" : 0, "total" : 0, "jobs" : 0, }

        if worker_row.state != 'disabled':
            worker_data[worker_key][worker_row.worker_type]['total'] += 1
            if worker_row.state not in ('dead', 'zombie'):
                worker_data[worker_key][worker_row.worker_type]['active'] += 1

    last_hour_timestamp = datetime.datetime.now() - datetime.timedelta(hours=1)


    build_rows = models.Build.objects.filter(state = 'complete',
                                             datetime__gt=last_hour_timestamp)
    for build_row in build_rows:
        worker_key = build_row.os_name + ' ' + build_row.os_version + ' ' + build_row.cpu_name
        worker_data[worker_key]['builder']['jobs'] += 1

    sitetestrun_rows = models.SiteTestRun.objects.filter(state = 'completed',
                                                         datetime__gt=last_hour_timestamp)
    for sitetestrun_row in sitetestrun_rows:
        worker_key = sitetestrun_row.os_name + ' ' + sitetestrun_row.os_version + ' ' + sitetestrun_row.cpu_name
        worker_data[worker_key]['crashtest']['jobs'] += 1

    unittestrun_rows = models.UnitTestRun.objects.filter(state = 'completed',
                                                         datetime__gt=last_hour_timestamp)
    for unittestrun_row in unittestrun_rows:
        worker_key = unittestrun_row.os_name + ' ' + unittestrun_row.os_version + ' ' + unittestrun_row.cpu_name
        worker_data[worker_key]['unittest']['jobs'] += 1

    worker_data_list = []
    for worker_key in worker_data:
        worker_data_list.append({'id'               : worker_key,
                                 'builder_active'   : worker_data[worker_key]['builder']['active'],
                                 'builder_total'    : worker_data[worker_key]['builder']['total'],
                                 'crashtest_active' : worker_data[worker_key]['crashtest']['active'],
                                 'crashtest_total'  : worker_data[worker_key]['crashtest']['total'],
                                 'crashtest_jobs'   : worker_data[worker_key]['crashtest']['jobs'],
                                 'unittest_active'  : worker_data[worker_key]['unittest']['active'],
                                 'unittest_total'   : worker_data[worker_key]['unittest']['total'],
                                 'unittest_jobs'    : worker_data[worker_key]['unittest']['jobs'],
                                 })

    worker_data_list.sort(cmp=lambda x, y: cmp(x['id'], y['id']))
    json = simplejson.dumps(worker_data_list)
    return HttpResponse(json, mimetype=APP_JS)

def worker_api(request, worker_id):
    json = serializers.serialize('json', [models.Worker.objects.get(pk=worker_id)])
    response = HttpResponse(json, mimetype=APP_JS)
    # Guh, shoot me.
    # Since the datetimes in the db are stored in local time, we need
    # to provide the server's local time to the client so it can provide
    # sensible defaults (e.g. for the last day's worth of logs).
    # We could also just return UTC offset...
    response['Sisyphus-Localtime'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    return response

@login_required
def worker_log_api(request, worker_id, start, end):
    logs = models.Log.objects.filter(worker__id__exact=worker_id)
    if start != '-':
        logs = logs.filter(datetime__gte=start)
    if end != '-':
        logs = logs.filter(datetime__lte=end)
    logs = logs.order_by('datetime').all()
    response = '[]'
    if request.method == 'GET':
        response = serializers.serialize("json", logs)
    elif request.method == 'DELETE':
        logs.delete()
    return HttpResponse(response, mimetype=APP_JS)

@login_required
def all_workers_log_api(request, start, end):
    logs = models.Log.objects
    if start != '-':
        logs = logs.filter(datetime__gte=start)
    if end != '-':
        logs = logs.filter(datetime__lte=end)
    logs = logs.order_by('datetime').select_related('worker')
    if request.method == 'GET':
        json = serializers.serialize("json", logs, relations={'worker': {'fields': ('hostname',)}})
        return HttpResponse(json, mimetype=APP_JS)
    if request.method == 'DELETE':
        logs.delete()
    return HttpResponse('[]', mimetype=APP_JS)

@csrf_exempt
def post_files(request):

    try:
        if request.method != 'POST':
            # http://docs.djangoproject.com/en/1.2/ref/request-response/#django.http.HttpResponseNotAllowed
            return HttpResponseNotAllowed(['POST'])

        logprefix = ("%s %s:" % (
                datetime.datetime.now().isoformat(),
                request.META["REMOTE_ADDR"]))

        # pass Model name, primary key, path, and a set of files via POST and save them
        # in the media/<path>/ directory. Each "file" field in the row contains
        # a full path to the uploaded file if it exists.

        error_list = []

        if 'pk' not in request.POST or not request.POST['pk']:
            # pk is the primary key of the row which will reference the uploaded file.
            error_list.append('Missing primary key')
        else:
            pk = request.POST['pk']

        if 'model_name' not in request.POST or not request.POST['model_name']:
            error_list.append('Missing Model name')
        else:
            model_name = request.POST['model_name']
            model      = eval('models.' + model_name)

        if 'dest_path' not in request.POST or not request.POST['dest_path']:
            error_list.append('Missing Model destination path')
        else:
            dest_path = request.POST['dest_path'].encode('utf-8')
            # allow relative paths contain subdirectories.
            reValidPath    = re.compile(r'^[\w][\w/-]+$')
            if not reValidPath.match(dest_path):
                error_list.append(dest_path + ' contains invalid characters')
            else:
                if not settings.MEDIA_ROOT:
                    error_list.append('MEDIA_ROOT not set')
                else:
                    dest_dir = os.path.join(settings.MEDIA_ROOT, dest_path)
                    if not os.path.exists(dest_dir):
                        try:
                            os.mkdir(dest_dir)
                        except Exception, e:
                            exceptionType, exceptionValue, errorMessage  = utils.formatException()
                            viewslog = open('/tmp/views.log', 'ab+')
                            viewslog.write("%s Exception: %s creating %s\n" % (logprefix, errorMessage, dest_dir))
                            viewslog.close()
        if not request.FILES:
            error_list.append('Missing file content')

        if error_list:
            viewslog = open('/tmp/views.log', 'ab+')
            viewslog.write('%s Bad Request: %s.\n' % (logprefix, ','.join(error_list)))
            viewslog.close()
            return HttpResponseBadRequest('Bad Request: %s.' % ','.join(error_list))

        try:
            row = model.objects.get(pk = pk)
        except model.DoesNotExist:
            return httpResponseNotFound('%s %s not found' % (model_name, pk))

        #http://docs.djangoproject.com/en/1.2/ref/request-response/#django.http.HttpRequest.FILES

        rfile = re.compile(r'^[\w,.-]*$')

        for fieldname, uploadedfile in request.FILES.items():

            filename    = uploadedfile.name

            if not rfile.match(filename):
                viewslog = open('/tmp/views.log', 'ab+')
                viewslog.write("%s bad filename: %s\n" % (logprefix, filename))
                viewslog.close()
                return HttpResponseBadRequest('Bad Request: filename %s' % filename)

            oldfilepath = eval('row.' + fieldname)
            newfilepath = os.path.join(dest_dir, filename).encode('utf-8')

            if oldfilepath:
                # If the current field value points to an existing file, unlink it.
                # We must do this prior to writing the new file since the old and
                # new may have the same file names.
                if os.path.exists(oldfilepath):
                    os.unlink(oldfilepath)

            row.__setattr__(fieldname, newfilepath)

            output = open(newfilepath, 'wb+')

            for chunk in uploadedfile.chunks():
                output.write(chunk)

            output.close()

        row.save()
        response = HttpResponseRedirect('/bughunter/media/')

    except:
        exceptionType, exceptionValue, errorMessage  = utils.formatException()
        viewslog = open('/tmp/views.log', 'wb+')
        viewslog.write("%s Exception: %s" % (logprefix, errorMessage))
        viewslog.close()
        response = HttpResponseServerError("ERROR: %s" % errorMessage)

    return response

@login_required
def workers_api(request):
    json = serializers.serialize('json', models.Worker.objects.order_by('hostname').all())
    return HttpResponse(json, mimetype=APP_JS)

def crashes_by_date(request, start, end, other_parms):
    other_parms_list = filter(lambda x: x, other_parms.split('/'))
    sql = """SELECT Crash.signature, fatal_message, SiteTestRun.branch, SiteTestRun.os_name, SiteTestRun.os_version, SiteTestRun.cpu_name, count( * )
FROM SocorroRecord, Crash, SiteTestCrash, SiteTestRun
WHERE Crash.id = SiteTestCrash.crash_id
AND SiteTestRun.id = SiteTestCrash.testrun_id
AND SocorroRecord.id = SiteTestRun.socorro_id
AND SiteTestRun.datetime >= %s"""
    sql_parms = [start]

    if end and end != '-':
        sql += '\nAND SiteTestRun.datetime < %s'
        sql_parms.append(end)
    if 'newonly' in other_parms_list:
        sql += """
AND Crash.id NOT
IN (
SELECT Crash.id
FROM Crash, SiteTestCrash
WHERE Crash.id = SiteTestCrash.crash_id
AND SiteTestCrash.datetime < %s
)"""
        sql_parms.append(start)

    sql += """
GROUP BY Crash.signature, fatal_message, SiteTestRun.branch, SiteTestRun.os_name, SiteTestRun.os_version, SiteTestRun.cpu_name
ORDER BY `SiteTestRun`.`fatal_message` DESC , Crash.signature ASC"""
    cursor = connection.cursor()
    cursor.execute(sql, sql_parms)

    # results are data[signature][fatal message][branch][platform] = <count>
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

    for row in cursor.fetchall():
        platform = '%s %s %s' % tuple(row[3:6])
        data[row[0]][row[1]][row[2]][platform] += row[6]

    response_data = []
    for signature, sig_matches in data.iteritems():
        for fatal_message, branches in sig_matches.iteritems():
            crash = { 'signature': signature,
                      'fatal_message': fatal_message,
                      'branches': branches }
            response_data.append(crash)

    return HttpResponse(simplejson.dumps(response_data), mimetype=APP_JS)
        








"""
Bughunter View Service Methods
"""
def bhview_setup(func):
   """
   This decorator initializes common data for VIEW_ADAPTERS.
   """
   def wrap(request, *a, **kw):
      ##Name of proc in json file##
      proc_name = os.path.basename(request.path)
      ##Base path to proc in json file##
      proc_path = "bughunter.views."
      ##Full proc name including base path in json file##
      full_proc_path = "%s%s" % (proc_path, proc_name)

      ##Get any placeholders##
      placeholders = []
      if 'p' in request.GET:
         placeholders = request.GET['p'].split(',')

      ##Get any replacements##
      replace_type = None
      replacements = []
      if 'r' in request.GET:
         replace_type = 'replace'
         replacements = request.GET['r'].split(',')

      ##Set replace_quote##
      if 'rq' in request.GET:
         replace_type = 'replace_quote'
         replacements = request.GET['rq'].split(',')

      ##Get any named fields##
      nfields = {} 
      for f in NAMED_FIELDS:
         if f in request.POST:
            if f == 'url':
               """
               NOTE: This is a hack to enable matching url's from the database that are utf-8 
                     encoded that contain non-english or non ASCII characters.  Django will encode them a 
                     second time before loading request.GET or request.POST and the browser 
                     also encodes them a second time when executing an HTTP GET using the XMLRequestObject.  
                     Once the url has been utf-8 encoded twice it cannot be accurately decoded
                     and will fail to match the single encoded url's stored in the database.
                       Switching the web service to use HTTP POST instead of GET ressolves 
                     the browser XMLRequestObject encoding problem and accessing the raw untreated
                     POST data through django's request.raw_post_data allows us to bypass having 
                     to use the corrupted url data in request.GET and request.POST.
                       This enables access to the url byte string which can be used to match the 
                     url stored in the database.  Pain and suffering... Jeads  
               """
               match = re.search('%s=(http.*?$)' % (f), request.raw_post_data)
               if match:
                  ###
                  # urllib.unquote_plus unquotes javascript's encodeURIComponent()
                  # DHUB.escapeString escapes strings for mysql which will prevent 
                  # SQL injection
                  ###
                  nfields[f] = settings.DHUB.escapeString( urllib.unquote_plus(match.group(1)) )
            else:
               if request.POST[f]:
                  nfields[f] = settings.DHUB.escapeString( urllib.unquote_plus(request.POST[f]) )

      kwargs = dict( proc_name=proc_name,
                     proc_path=proc_path,
                     full_proc_path=full_proc_path,
                     placeholders=placeholders,
                     replacements=replacements,
                     replace_type=replace_type,
                     named_fields=nfields )

      return func(request, **kwargs)

   return wrap

@csrf_exempt
def view_login(request):

    if request.method != 'POST':
        ##User loads page##  
        return render_to_response('bughunter.login.html', {})

    username = request.POST['username']
    password = request.POST['password']

    user = authenticate(username=username, password=password)

    if not user or not user.is_active:
        m = {'error_message':'incorrect username or password'}
        return render_to_response('bughunter.login.html', m)
    else:
        login(request, user)
        return HttpResponseRedirect(settings.VIEW_LANDING_PAGE)

def view_logout(request):
    logout(request)
    return HttpResponseRedirect(settings.VIEW_LOGIN_PAGE)

@csrf_exempt
@login_required
def bhview(request, target=settings.VIEW_LOGIN_PAGE):

    get_token(request)
    request.META["CSRF_COOKIE_USED"] = True

    signals = []
    for f in NAMED_FIELDS:
      if f in request.POST:
         signals.append( { 'value':request.POST[f], 'name':f } )

    start_date, end_date = _get_date_range()

    data = { 'username':request.user.username,
             'start_date':start_date,
             'end_date':end_date,
             'signals':signals }

    return render_to_response('bughunter.views.html', data)

@bhview_setup
@login_required
def get_bhview(request, **kwargs):
   """
   The goal of the get_bhview webservice is to be able to add
   new service methods by simply adding a new sql view to 
   the data proc file bughunter.json.  It works off of the 
   following url structure:   

   /views/viewname?p=PLACEHOLDERS&r=REPLACE&rq=REPLACE_QUOTE&named_field=VALUE

   viewname - Could be a data hub proc name or a key in 
              VIEW_ADAPTERS.  VIEW_ADAPTERS is a dictionary that maps
              viewnames requiring special handling to function 
              references that can handle them.  This allows 
              adapters to call multiple procs if required or
              do something more extravagant.  When no adapter 
              is available for a view name it's assumed that the 
              viewname will be found in proc_path = "bughunter.views."
              in the data hub proc json file.

   The arguments p, r, rq, and named_field are optional, if set 
   they translate to options for settings.DHUB.execute():

   See the datasource README for more documentation

   p=placeholders
   r=replace
   rq=replace_quote
   named_field= The named_fields other than p,r,rq require a
                view_adapter to manage their incorporation into
                an arguments to execute().

   settings.DHUB.execute( proc=viewname,
                          placeholders=PLACEHOLDERS,
                          replace|replace_quote=REPLACE|REPLACE_QUOTE )

   To add a new service method add SQL to bughunter.json and you're
   done unless you require named fields.  If you cannot get what you 
   want with a single SQL statement add an adapter function reference 
   to VIEW_ADAPTERS and do something awesome.
   """
   ##Populated by bhview_decorator##
   proc_name = kwargs['proc_name']
   proc_path = kwargs['proc_path']
   full_proc_path = kwargs['full_proc_path']
   placeholders = kwargs['placeholders']
   replacements = kwargs['replacements']
   replace_type = kwargs['replace_type']
   nfields = kwargs['named_fields']

   ##options for execute##
   exec_args = dict()

   if placeholders:
      exec_args['placeholders'] = placeholders
   if replacements:
      exec_args[replace_type] = replacements

   json = ""
   if proc_name in VIEW_ADAPTERS:
      ####
      #Found a data adapter for the proc, call it
      ####
      json = VIEW_ADAPTERS[proc_name](proc_path, 
                                      proc_name, 
                                      full_proc_path, 
                                      placeholders, 
                                      replacements,
                                      nfields)
   else:
      ####
      #Default behavior for a view
      ####
      exec_args['proc'] = full_proc_path
      exec_args['return_type'] = 'tuple_json'

      ####
      # Uncomment this line to see fully assembled
      # SQL in the server log.  Useful for debugging.
      #exec_args['debug_show'] = True
      json = settings.DHUB.execute(**exec_args)
   
   return HttpResponse(json, mimetype=APP_JS)
   
def _get_new_crashes(proc_path, proc_name, full_proc_path, placeholders, replacements, nfields):

   col_prefixes = { 'start_date':'str',
                    'end_date':'str',
                    'date_only':'str'}

   rep_dict = _build_rep(nfields, col_prefixes)

   rep0 = rep_dict['full_where'] 
   if not rep0:
      rep0 = rep_dict['date_only']

   #_build_rep could produce an extra AND at the beginning of the string
   #so remove it here.
   rp = re.compile('^\s+AND')
   rep0 = rp.sub('', rep0, count=1)

   json = settings.DHUB.execute(proc=full_proc_path,
                                replace=[ rep0 ],
                                #debug_show=True,
                                return_type='tuple_json')

   return json

def _get_site_test_crash(proc_path, proc_name, full_proc_path, placeholders, replacements, nfields):

   prefix = 'stc'
   sig_prefix = 'c'

   col_prefixes = { 'start_date':prefix,
                    'end_date':prefix,
                    'signature':sig_prefix,
                    'url':prefix,
                    'date_only':prefix }

   rep_dict = _build_rep(nfields, col_prefixes)

   #default to date_only if no fields were provided
   rep0 = rep_dict['full_where'] 
   if not rep0:
      rep0 = rep_dict['date_only']

   #_build_rep could produce an extra AND at the beginning of the string
   #so remove it here.
   rp = re.compile('^\s+AND')
   rep0 = rp.sub('', rep0, count=1)

   json = settings.DHUB.execute(proc=full_proc_path,
                                replace=[ rep0 ],
                                #debug_show=True,
                                return_type='tuple_json')

   return json

def _get_socorro_record(proc_path, proc_name, full_proc_path, placeholders, replacements, nfields):

   col_prefixes = { 'start_date':'str',
                    'end_date':'str',
                    'signature':'sr',
                    'url':'sr',
                    'date_only':'str' }

   rep_dict = _build_rep(nfields, col_prefixes)

   #default to date_only if no fields were provided
   rep0 = rep_dict['full_where'] 
   if not rep0:
      rep0 = rep_dict['date_only']

   #_build_rep could produce an extra AND at the beginning of the string
   #so remove it here.
   rp = re.compile('^\s+AND')
   rep0 = rp.sub('', rep0, count=1)

   json = settings.DHUB.execute(proc=full_proc_path,
                                replace=[ rep0 ],
                                #debug_show=True,
                                return_type='tuple_json')

   return json

def _get_crash_detail(proc_path, proc_name, full_proc_path, placeholders, replacements, nfields):

   col_prefixes = { 'start_date':'stc',
                    'end_date':'stc',
                    'signature':'c',
                    'url':'sr',
                    'fatal_message':'str',
                    'date_only':'stc'}

   rep_dict = _build_rep(nfields, col_prefixes)

   date_only = ""
   if rep_dict['date_only']:
      date_only = " %s %s " % ('WHERE', rep_dict['date_only'])

   json = settings.DHUB.execute(proc=full_proc_path,
                                replace=[ date_only, rep_dict['full_where'] ],
                                #debug_show=True,
                                return_type='tuple_json')

   return json

def _get_crashes(proc_path, proc_name, full_proc_path, placeholders, replacements, nfields):

   col_prefixes = { 'start_date':'str',
                    'end_date':'str',
                    'signature':'c',
                    'url':'sr',
                    'fatal_message':'str',
                    'date_only':'str'}

   rep_dict = _build_rep(nfields, col_prefixes)

   #default to date_only if no fields were provided
   rep0 = rep_dict['full_where'] 
   if not rep0:
      rep0 = rep_dict['date_only']

   #_build_rep could produce an extra AND at the beginning of the string
   #so remove it here.
   rp = re.compile('^\s+AND')
   rep0 = rp.sub('', rep0, count=1)

   json = settings.DHUB.execute(proc=full_proc_path,
                                #debug_show=True,
                                replace=[ rep0 ],
                                return_type='tuple_json')

   return json

def _get_urls(proc_path, proc_name, full_proc_path, placeholders, replacements, nfields):

   col_prefixes = { 'start_date':'stc',
                    'end_date':'stc',
                    'signature':'c',
                    'url':'stc',
                    'date_only':'stc'}

   rep_dict = _build_rep(nfields, col_prefixes)

   #default to date_only if no fields were provided
   rep0 = rep_dict['full_where'] 
   if not rep0:
      rep0 = rep_dict['date_only']

   #_build_rep could produce an extra AND at the beginning of the string
   #so remove it here.
   rp = re.compile('^\s+AND')
   rep0 = rp.sub('', rep0, count=1)

   json = settings.DHUB.execute(proc=full_proc_path,
                                #debug_show=True,
                                replace=[ rep0 ],
                                return_type='tuple_json')

   return json

def _get_fmurls(proc_path, proc_name, full_proc_path, placeholders, replacements, nfields):

   col_prefixes = { 'start_date':'str',
                    'end_date':'str',
                    'fatal_message':'str',
                    'url':'stc',
                    'date_only':'str'}

   rep_dict = _build_rep(nfields, col_prefixes)

   #default to date_only if no fields were provided
   rep0 = rep_dict['full_where'] 
   if not rep0:
      rep0 = rep_dict['date_only']

   #_build_rep could produce an extra AND at the beginning of the string
   #so remove it here.
   rp = re.compile('^\s+AND')
   rep0 = rp.sub('', rep0, count=1)
   ####
   #Run the select on the temporary table
   ####
   json = settings.DHUB.execute(proc="%s%s" % (proc_path, 'urls_fm'),
                                #debug_show=True,
                                replace=[rep0],
                                return_type='tuple_json')

   return json

def _build_rep(nfields, col_prefixes):

   rep = {'date_only':'', 'full_where':''}

   if nfields:
      if ('start_date' in nfields) and ('end_date' in nfields):
         rep['full_where'] += " AND (%s.datetime >= '%s' AND %s.datetime <= '%s') " % \
         (col_prefixes['start_date'], nfields['start_date'], col_prefixes['end_date'], nfields['end_date'])

         ##Enables a nested query that needs the date range only##
         rep['date_only'] = " (%s.datetime >= '%s' AND %s.datetime <= '%s') " % \
         (col_prefixes['start_date'], nfields['start_date'], col_prefixes['end_date'], nfields['end_date'])

      elif ('start_date' in nfields):
         rep['full_where'] += " %s.datetime >= '%s' " % \
         (col_prefixes['start_date'], nfields['start_date'])

      elif ('end_date' in nfields):
         ##Add a start date##
         start, end = _get_date_range()
         rep['full_where'] += " AND (%s.datetime >= '%s' AND %s.datetime <= '%s') " % \
         (col_prefixes['start_date'], start, col_prefixes['end_date'], nfields['end_date'])

      ##Build all other fields##
      for field in NAMED_FIELDS:
         if (field == 'start_date') or (field == 'end_date'):
            continue
         if (field in nfields) and (field in col_prefixes):
            rep['full_where'] += " AND %s.%s='%s' " % (col_prefixes[field], field, nfields[field])

   else:
      ##Handling for no fields##
      start, end = _get_date_range()
      rep['date_only'] = " %s.datetime >= '%s' AND %s.datetime <= '%s' " % \
      (col_prefixes['date_only'], start, col_prefixes['date_only'], end) 

   return rep

def _get_date_range():

   #start_date = datetime.date.today() - datetime.timedelta(hours=48)
   start_date = datetime.date.today() - datetime.timedelta(hours=120)
   end_date = datetime.date.today()

   return start_date, end_date

####
#VIEW_ADAPTERS maps view names to function
#references that handle them.  All adapters
#need to return json
####
VIEW_ADAPTERS = dict( crashes=_get_crashes,
                      site_test_crash=_get_site_test_crash,
                      urls=_get_urls,
                      fmurls=_get_fmurls,
                      crashdetail=_get_crash_detail,
                      newcrashes=_get_new_crashes,
                      socorro_record=_get_socorro_record)

NAMED_FIELDS = set( ['signature',
                     'url',
                     'fatal_message',
                     'start_date',
                     'end_date'] )

VIEW_PAGES = set([ 'bhview' ])



