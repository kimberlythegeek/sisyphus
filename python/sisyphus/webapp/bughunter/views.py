import os
import math
import sys
import re
import datetime
import time
import simplejson
import urllib

from base64 import b64encode
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

from sisyphus.webapp.bughunter import models
from sisyphus.automation import utils
from sisyphus.automation.crashtest import crashurlloader

###
# Returns a random string with specified number of characters.  Adapted from
# http://code.activestate.com/recipes/576722-pseudo-random-string/
###
get_rand_str = lambda n: b64encode( os.urandom(int(math.ceil(0.75*n))), '__')[:n]

APP_JS = 'application/json'

####
#ADMIN APPLICATION SERVICE METHODS
####
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

    worker_rows = models.Worker.objects.exclude(state='disabled')

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
        # Clear Logs should clear entire log, not just displayed entries.
        models.Log.objects.all().delete()
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
                            os.makedirs(dest_dir)
                        except Exception, e:
                            exceptionType, exceptionValue, errorMessage  = utils.formatException()
                            sys.stderr.write("%s Exception: %s creating %s.\n" % (logprefix, errorMessage, dest_dir))
        if not request.FILES:
            error_list.append('Missing file content')

        if error_list:
            sys.stderr.write('%s Bad Request: %s.\n' % (logprefix, ','.join(error_list)))
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
                sys.stderr.write("%s bad filename: %s.\n" % (logprefix, filename))
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
        sys.stderr.write("%s Exception: %s.\n" % (logprefix, errorMessage))
        response = HttpResponseServerError("ERROR: %s" % errorMessage)

    return response

@login_required
def workers_api(request):
    json = serializers.serialize('json', models.Worker.objects.order_by('hostname').exclude(state='disabled'))
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
        
####
#BUGHUNTER VIEW SERVICE METHODS
####

####
#VIEW SERVICE DECORATORS
####
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
                  nfields[f] = settings.DHUB.escapeString( urllib.unquote(match.group(1)) )
            else:
               if request.POST[f]:
                  nfields[f] = settings.DHUB.escapeString( urllib.unquote(request.POST[f]) )

      kwargs = dict( proc_name=proc_name,
                     proc_path=proc_path,
                     full_proc_path=full_proc_path,
                     named_fields=nfields )

      return func(request, **kwargs)

   return wrap

####
#VIEW SERVICE METHODS WITH URL MAPPINGS
####
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

    ####
    #Load any signals provided in the page
    ####
    signals = []
    start_date, end_date = _get_date_range()

    for f in NAMED_FIELDS:
      if f in request.POST:
         if f == 'start_date':
            start_date = datetime.date( *time.strptime(request.POST[f], '%Y-%m-%d')[0:3] )
         elif f == 'end_date':
            end_date = datetime.date( *time.strptime(request.POST[f], '%Y-%m-%d')[0:3] )
         else:
            signals.append( { 'value':urllib.unquote( request.POST[f] ), 'name':f } )

    data = { 'username':request.user.username,
             'start_date':start_date,
             'end_date':end_date,
             'current_date':datetime.date.today(),
             'signals':signals }

    ##Caller has provided the view parent of the signals, load in page##
    parentIndexKey = 'parent_bhview_index'
    if parentIndexKey in request.POST:
      data[parentIndexKey] = request.POST[parentIndexKey]

    return render_to_response('bughunter.views.html', data)

@login_required
def get_help(request, target=settings.VIEW_LOGIN_PAGE):
   get_token(request)
   request.META["CSRF_COOKIE_USED"] = True
   data = {}
   return render_to_response('help/bughunter.generic.help.html', data)

@login_required
def get_date_range(request, **kwargs):

   start_date, end_date = _get_date_range()
   current_date = datetime.date.today()
   json = simplejson.dumps( { 'start_date':str(start_date), 
                              'end_date':str(end_date),
                              'current_date':str(current_date) } )

   return HttpResponse(json, mimetype=APP_JS)

@login_required
def resubmit_urls(request):
   
   get_token(request)
   request.META["CSRF_COOKIE_USED"] = True

   raw_data = simplejson.loads(request.raw_post_data)

   urls = []
   comments = ""
   escape_func = settings.DHUB.escapeString;

   if 'urls' in raw_data:
      for url in raw_data['urls']:
         urls.append( urllib.unquote(url) )

   if 'comments' in raw_data:
      comments = escape_func( urllib.unquote(raw_data['comments']) )

   data = { 'urls':urls,
            'signature':raw_data['comments'],
            'skipurls':[],
            'user_id':request.user.id,
            'skipurlsfile':""}

   response = crashurlloader.load_urls(data, True)
   json = simplejson.dumps( { 'message':response } )

   return HttpResponse(json, mimetype=APP_JS)

@bhview_setup
@login_required
def get_bhview(request, **kwargs):
   """
   The goal of the get_bhview webservice is to be able to add
   new service methods by simply adding a new sql view to 
   the data proc file bughunter.json.  It works off of the 
   following url structure:   

   /views/viewname?named_field=VALUE

   viewname - Could be a data hub proc name or a key in 
              VIEW_ADAPTERS.  VIEW_ADAPTERS is a dictionary that maps
              viewnames requiring special handling to function 
              references that can handle them.  This allows 
              adapters to call multiple procs if required or
              do something more extravagant.  When no adapter 
              is available for a view name it's assumed that the 
              viewname will be found in proc_path = "bughunter.views."
              in the data hub proc json file.

   See the datasource README for more documentation

   named_field= The named_fields require a view_adapter to manage 
                their incorporation into an arguments to execute().

   To add a new service method add SQL to bughunter.json and you're
   done unless you require named fields.  If you cannot get what you 
   want with a single SQL statement add an adapter function reference 
   to VIEW_ADAPTERS and do something awesome.
   """
   ##Populated by bhview_decorator##
   proc_name = kwargs['proc_name']
   proc_path = kwargs['proc_path']
   full_proc_path = kwargs['full_proc_path']
   nfields = kwargs['named_fields']

   if settings.DEBUG:
      ###
      #Write IP address and datetime to log
      ###
      print "Client IP:%s" % (request.META['REMOTE_ADDR'])
      print "Request Datetime:%s" % (str(datetime.datetime.now()))

   json = ""
   if proc_name in VIEW_ADAPTERS:
      ####
      #Found a data adapter for the proc, call it
      ####
      if proc_name in settings.CACHE_QUERIES:
         #####
         #Use cache query for developing/debugging purposes
         #####
         json = simplejson.dumps( settings.CACHE_QUERIES[proc_name] )
      else:
         json = VIEW_ADAPTERS[proc_name](proc_path, 
                                         proc_name, 
                                         full_proc_path, 
                                         nfields,
                                         request.user.id)
   else:
      json = '{ "error":"Data view name %s not recognized" }' % proc_name

   return HttpResponse(json, mimetype=APP_JS)

####
#USER DATA: URL Resubmissions
####
def _get_resubmission_urls(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'sr',
                    'url':'sr' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], str(user_id), rep ],
                                       return_type='table')

   response_data = _aggregate_user_data(table_struct)

   columns = [ 'Date',
               'signature',
               'url',
               'status',
               'Total Count']

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_all_resubmission_urls(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'sr',
                    'url':'sr' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_all_user_data(table_struct)

   columns = [ 'User',
               'Date',
               'signature',
               'url',
               'status',
               'Total Count']

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

#####
#SITE TESTING DATA ADAPTERS: Crashes
#####
def _get_crashes_st(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'c',
                    'fatal_message':'str',
                    'url':'stc',
                    'address':'stc',
                    'pluginfilename':'stc',
                    'pluginversion':'stc',
                    'exploitability':'stc' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   if ('new_signatures' in nfields) and (nfields['new_signatures'] == 'on'):
      full_proc_path = proc_path + 'new_crash_signatures_st'

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_crashes_platform_data(table_struct)
   
   columns = [ 'signature', 
               'fatal_message', 
               'Total Count', 
               'Platform' ]

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_crash_urls_st(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'c',
                    'url':'stc',
                    'fatal_message':'str',
                    'address':'stc',
                    'pluginfilename':'stc',
                    'pluginversion':'stc',
                    'exploitability':'stc' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_url_platform_data(table_struct)

   columns = ['url', 'Total Count', 'Platform']

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_crash_detail_st(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'c',
                    'url':'stc',
                    'fatal_message':'str',
                    'address':'stc',
                    'pluginfilename':'stc',
                    'pluginversion':'stc',
                    'exploitability':'stc' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   temp_table_name = 'temp_urls_st_' + get_rand_str(8)

   ##Build temp table##
   settings.DHUB.execute(proc=proc_path + 'temp_urls_st',
                         debug_show=settings.DEBUG,
                         replace=[ nfields['start_date'], nfields['end_date'], rep, temp_table_name ])

   ##Get the crashdetails##
   data = settings.DHUB.execute(proc=full_proc_path,
                                debug_show=settings.DEBUG,
                                replace=[ nfields['start_date'], nfields['end_date'], temp_table_name ],
                                return_type='table')

   ##Remove temp table##
   settings.DHUB.execute(proc=proc_path + 'drop_temp_table',
                         debug_show=settings.DEBUG,
                         replace=[ temp_table_name ])

   return simplejson.dumps( {'columns':data['columns'], 
                             'data':data['data'], 
                             'start_date':nfields['start_date'], 
                             'end_date':nfields['end_date']} )
#####
#SITE TESTING DATA ADAPTERS: Assertions
#####
def _get_assertions_st(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'assertion':'a',
                    'location':'a',
                    'url':'sta' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   if ('new_signatures' in nfields) and (nfields['new_signatures'] == 'on'):
      full_proc_path = proc_path + 'new_assertions_st'

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_assertion_platform_data(table_struct)
   
   columns = [ 'assertion', 
               'location', 
               'Occurrence Count',
               'Total Count', 
               'Platform' ]

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_assertion_urls_st(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'url':'sta',
                    'assertion':'a' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_url_platform_data(table_struct)

   columns = ['url', 'Occurrence Count', 'Total Count', 'Platform']

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_assertion_detail_st(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'assertion':'a',
                    'location':'a', 
                    'url':'sta' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   temp_table_name = 'temp_assertion_urls_st_' + get_rand_str(8)

   ##Build temp table##
   settings.DHUB.execute(proc=proc_path + 'temp_assertion_urls_st',
                         debug_show=settings.DEBUG,
                         replace=[ nfields['start_date'], nfields['end_date'], rep, temp_table_name ])

   ##Get the assertiondetails##
   data = settings.DHUB.execute(proc=full_proc_path,
                                debug_show=settings.DEBUG,
                                replace=[ nfields['start_date'], nfields['end_date'], temp_table_name ],
                                return_type='table')

   ##Remove temp table##
   settings.DHUB.execute(proc=proc_path + 'drop_temp_table',
                         debug_show=settings.DEBUG,
                         replace=[ temp_table_name ])

   return simplejson.dumps( {'columns':data['columns'], 
                             'data':data['data'], 
                             'start_date':nfields['start_date'], 
                             'end_date':nfields['end_date']} )

#####
#UNIT TESTING ADAPTERS
#####
def _get_crashes_ut(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'c',
                    'url':'sr',
                    'fatal_message':'str',
                    'address':'stc',
                    'pluginfilename':'stc',
                    'pluginversion':'stc',
                    'exploitability':'stc' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   if ('new_signatures' in nfields) and (nfields['new_signatures'] == 'on'):
      full_proc_path = proc_path + 'new_crash_signatures_ut'

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_crashes_platform_data(table_struct)
   
   columns = [ 'signature', 
               'fatal_message', 
               'Total Count', 
               'Platform' ]

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_assertions_ut(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'assertion':'a',
                    'location':'a' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   if ('new_signatures' in nfields) and (nfields['new_signatures'] == 'on'):
      full_proc_path = proc_path + 'new_assertions_ut'

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_assertion_platform_data(table_struct)
   
   columns = [ 'assertion', 
               'location', 
               'Occurrence Count',
               'Total Count', 
               'Platform' ]

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_assertion_detail_ut(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'assertion':'a',
                    'location':'a', 
                    'url':'uta' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   temp_table_name = 'temp_assertion_urls_ut_' + get_rand_str(8)

   ##Build temp table##
   settings.DHUB.execute(proc=proc_path + 'temp_assertion_urls_ut',
                         debug_show=settings.DEBUG,
                         replace=[ nfields['start_date'], nfields['end_date'], rep, temp_table_name ])

   ##Get the assertiondetails##
   data = settings.DHUB.execute(proc=full_proc_path,
                                debug_show=settings.DEBUG,
                                replace=[ nfields['start_date'], nfields['end_date'], temp_table_name ],
                                return_type='table')

   ##Remove temp table##
   settings.DHUB.execute(proc=proc_path + 'drop_temp_table',
                         debug_show=settings.DEBUG,
                         replace=[ temp_table_name ])

   return simplejson.dumps( {'columns':data['columns'], 
                             'data':data['data'], 
                             'start_date':nfields['start_date'], 
                             'end_date':nfields['end_date']} )

def _get_assertion_urls_ut(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'url':'uta',
                    'assertion':'a' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_url_platform_data(table_struct)

   columns = ['url', 'Occurrence Count', 'Total Count', 'Platform']

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

#####
#UNIT TESTING VALGRIND ADAPTERS
#####
def _get_valgrinds_ut(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'v',
                    'message':'v' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   if ('new_signatures' in nfields) and (nfields['new_signatures'] == 'on'):
      full_proc_path = proc_path + 'new_valgrinds_ut'

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_valgrind_platform_data(table_struct)
   
   columns = [ 'signature', 
               'message', 
               'Total Count', 
               'Platform' ]

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_valgrind_urls_ut(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'url':'utv',
                    'message':'v',
                    'signature':'v' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   table_struct = settings.DHUB.execute(proc=full_proc_path,
                                       debug_show=settings.DEBUG,
                                       replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                       return_type='table')

   response_data = _aggregate_url_platform_data(table_struct)

   columns = ['url', 'Total Count', 'Platform']

   return simplejson.dumps( { 'columns':columns, 
                              'data':response_data,
                              'start_date':nfields['start_date'], 
                              'end_date':nfields['end_date'] } )

def _get_valgrind_detail_ut(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'v',
                    'message':'v', 
                    'url':'utv' }

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   temp_table_name = 'temp_valgrind_urls_ut_' + get_rand_str(8)

   ##Build temp table##
   settings.DHUB.execute(proc=proc_path + 'temp_valgrind_urls_ut',
                         debug_show=settings.DEBUG,
                         replace=[ nfields['start_date'], nfields['end_date'], rep, temp_table_name ])

   ##Get the assertiondetails##
   data = settings.DHUB.execute(proc=full_proc_path,
                                debug_show=settings.DEBUG,
                                replace=[ nfields['start_date'], nfields['end_date'], temp_table_name ],
                                return_type='table')

   ##Remove temp table##
   settings.DHUB.execute(proc=proc_path + 'drop_temp_table',
                         debug_show=settings.DEBUG,
                         replace=[ temp_table_name ])

   return simplejson.dumps( {'columns':data['columns'], 
                             'data':data['data'], 
                             'start_date':nfields['start_date'], 
                             'end_date':nfields['end_date']} )

#####
#CRASH TABLE ADAPTERS
#####
def _get_socorro_record(proc_path, proc_name, full_proc_path, nfields, user_id):

   col_prefixes = { 'signature':'sr',
                    'url':'sr',
                    'socorro_id':'sr'}

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   proc = full_proc_path
   column_name = 'socorro_id'
   replace_list = [ nfields['start_date'], nfields['end_date'], rep ]

   #####
   #If we have an id don't use the date range.  The date
   #range will not necessarily match in socorro_record and
   #we're only returning one row so we don't need it.
   #####
   if rep.find(column_name) > -1:
      ###
      #In the socorro table sororro_id corresponds to the
      #id column
      ###
      rep = rep.replace('socorro_id', 'id').replace('AND', '')
      proc = proc_path + 'socorro_record_no_date'
      replace_list = [rep]

   data = settings.DHUB.execute(proc=proc,
                                debug_show=settings.DEBUG,
                                replace=replace_list,
                                return_type='table')

   return simplejson.dumps( {'columns':data['columns'], 
                             'data':data['data'], 
                             'start_date':nfields['start_date'], 
                             'end_date':nfields['end_date']} )

#####
#PLATFORM AGGREGATION METHODS
#####
def _aggregate_crashes_platform_data(table_struct):

   #####
   #Aggregate the os_name, os_version, and cpu_name by branch
   #####
   data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))))

   for row in table_struct['data']:

      cpu_data = _format_cpu_data(row)

      platform = '%s %s %s <b>%s</b>' % (row['os_name'], row['os_version'], cpu_data, row['total_count'])
      data[row['signature']][row['fatal_message']][row['branch']][platform]['total_count'] += row['total_count']

   response_data = []
   for signature, sig_matches in data.iteritems():
      for fatal_message, branches in sig_matches.iteritems():

         total_count, platform, aggregation_count = _format_branch_data(branches)

         crash = { 'signature': signature,
                   'fatal_message': fatal_message,
                   'Platform': platform,
                   'Total Count':total_count}

         response_data.append(crash)

   return response_data

def _aggregate_assertion_platform_data(table_struct):

   #####
   #Aggregate the os_name, os_version, and cpu_name by branch
   #####
   data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))))

   for row in table_struct['data']:

      cpu_data = _format_cpu_data(row)

      platform = '%s %s %s <b>%s</b>' % (row['os_name'], row['os_version'], cpu_data, row['total_count'])
      data[row['assertion']][row['location']][row['branch']][platform]['total_count'] += int(row['total_count'])
      data[row['assertion']][row['location']][row['branch']][platform]['occurrence_count'] += int(row['occurrence_count'])

   response_data = []
   for assertion, matches in data.iteritems():

      occurrence_count = 0

      for location, branches in matches.iteritems():

         total_count, formated_platform, occurrence_count = _format_branch_data(branches)

         crash = { 'assertion': assertion,
                   'location': location,
                   'Platform': formated_platform,
                   'Total Count':total_count,
                   'Occurrence Count':occurrence_count}

         response_data.append(crash)

   return response_data

def _aggregate_valgrind_platform_data(table_struct):

   #####
   #Aggregate the os_name, os_version, and cpu_name by branch
   #####
   data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int)))))

   for row in table_struct['data']:

      cpu_data = _format_cpu_data(row)

      platform = '%s %s %s <b>%s</b>' % (row['os_name'], row['os_version'], cpu_data, row['total_count'])
      data[row['signature']][row['message']][row['branch']][platform]['total_count'] += int(row['total_count'])

   response_data = []
   for signature, matches in data.iteritems():

      occurrence_count = 0

      for message, branches in matches.iteritems():

         total_count, formated_platform, occurrence_count = _format_branch_data(branches)

         crash = { 'signature': signature,
                   'message': message,
                   'Platform': formated_platform,
                   'Total Count':total_count }

         response_data.append(crash)

   return response_data

def _aggregate_url_platform_data(table_struct):

   #####
   #Aggregate the os_name, os_version, and cpu_name by branch
   #####
   data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

   for row in table_struct['data']:

      cpu_data = _format_cpu_data(row)

      platform = '%s %s %s <b>%s</b>' % (row['os_name'], row['os_version'], cpu_data, row['total_count'])
      data[row['url']][row['branch']][platform]['total_count'] += int(row['total_count'])

      if 'occurrence_count' in row:
         data[row['url']][row['branch']][platform]['occurrence_count'] += int(row['occurrence_count'])

   response_data = []
   for url, branches in data.iteritems():

      total_count, platform, occurence_count = _format_branch_data(branches)

      url_summary = { 'Occurrence Count': occurence_count,
                      'Total Count':total_count, 
                      'url': url,
                      'Platform': platform }

      response_data.append(url_summary)

   return response_data

def _aggregate_user_data(table_struct):

   data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

   for row in table_struct['data']:

      ##Don't wrap the date##
      row['date'] = '<span class="no-wrap">' + row['date'] + '</span>'

      ####
      #Aggregate the state
      ####
      data[ row['signature'] ][ row['url'] ][ row['state'] ] += int(row['total_count'])
      data[ row['signature'] ][ row['url'] ][ 'total_count' ] += int(row['total_count'])
      data[ row['signature'] ][ row['url'] ][ 'date' ] = row['date']

   response_data = []
   status_list = ['waiting', 'executing', 'completed']
   for sig, sig_object in data.iteritems():
      for url in sig_object.keys():
         status_object = sig_object[url]

         ##format the status as a single string##
         status = _format_status_field(status_object, status_list)

         url_summary = { 'Date':status_object['date'],
                         'signature':sig,
                         'url':url,
                         'status':status,
                         'Total Count':status_object['total_count'] }

         response_data.append(url_summary)

   return response_data

def _format_status_field(status_object, status_list):

   status = ""
   for s in status_list:
      if s in status_object:
         ##uppercase first character##
         statusText = s[0].upper() + s[1:len(s)]
         count = status_object[s]

         if s == 'completed':
            if int(status_object[s]) == status_object['total_count']:
               ##All jobs are complete, set status and exit loop##
               status = '<span class="no-wrap bh-status-completed">ALL JOBS COMPLETE</span>'
               break
            else:
               status +='<span class="bh-status-' + s + '"><b>' + statusText + ':</b>' + str(count) + '</span>'
         else:
            status += '<span class="bh-status-' + s + '"><b>' + statusText + ':</b>' + str(count) + '</span>&nbsp;&nbsp;'

   return status

def _aggregate_all_user_data(table_struct):

   data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

   for row in table_struct['data']:

      ##Don't wrap the date##
      row['date'] = '<span class="no-wrap">' + row['date'] + '</span>'

      ####
      #Aggregate the state
      ####
      data[ row['email'] ][ row['signature'] ][ row['url'] ][ row['state'] ] += int(row['total_count'])
      data[ row['email'] ][ row['signature'] ][ row['url'] ][ 'total_count' ] += int(row['total_count'])
      data[ row['email'] ][ row['signature'] ][ row['url'] ][ 'date' ] = row['date']

   response_data = []
   status_list = ['waiting', 'executing', 'completed']
   for email, email_object in data.iteritems():
      for sig, sig_object in email_object.iteritems():
         for url in sig_object.keys():
            status_object = sig_object[url]

            ##format the status as a single string##
            status = _format_status_field(status_object, status_list)

            url_summary = {'User':email, 
                           'Date':status_object['date'],
                           'signature':sig,
                           'url':url,
                           'status':status,
                           'Total Count':status_object['total_count'] }

            response_data.append(url_summary)

   return response_data

def _format_branch_data(branches):

   platform = "" 
   counts_broken_down = "" 
   total_count = 0
   occurrence_count = 0

   ##Build the platform string, sort branches alphabetically##
   for branch in sorted(branches.keys()):
      counts_broken_down += "<b>%s</b>:&nbsp;&nbsp;&nbsp;" % branch
      for line in branches[branch]: 
         counts_broken_down += "%s&nbsp;&nbsp;&nbsp;" % line.replace(' ', '&nbsp;')

         if 'total_count' in branches[branch][line]:
            total_count += branches[branch][line]['total_count']

         if 'occurrence_count' in branches[branch][line]:
            occurrence_count += branches[branch][line]['occurrence_count']

      counts_broken_down += "<br />"
      platform += counts_broken_down
      counts_broken_down = ""

   return total_count, platform, occurrence_count

def _format_cpu_data(row):

   architecture = ""
   cpu_bits = "32"
   build_cpu_bits = "32"

   if row['cpu_name'].find('_') > -1:
      cpu_parts = row['cpu_name'].split('_')
      architecture = cpu_parts[0]
      cpu_bits = cpu_parts[1]
   else:
      architecture = row['cpu_name']

   if row['build_cpu_name'].find('_') > -1:
      build_cpu_bits = row['build_cpu_name'].split('_')[1]
      
   cpu_data = "%s %s/%s" % (architecture, cpu_bits, build_cpu_bits)

   return cpu_data

#####
#UTILITY METHODS
#####
def _get_date_range():

   start_date = datetime.date.today() - datetime.timedelta(hours=24)
   end_date = datetime.date.today() + datetime.timedelta(hours=24)

   return start_date, end_date

def _get_datetime_from_string(datestring):

   ####
   #The regex and match parsing was adapted from doParseDate above.  The return
   #values have been modified to support timedeltas with date + timestamps.
   ####

   ##Set fallback to today's date if match fails##
   dt = datetime.date.today()

   ##Parse the datestring and hope for the best##
   datestring = datestring.strip()
   m = re.match("^(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)(?: (?P<hour>\d\d)(?::(?P<minute>\d\d)(?::(?P<second>\d\d))?)?)?$", datestring)
   if m:
      date = (int(m.group("year")), int(m.group("month")), int(m.group("day")),
               m.group("hour") and int(m.group("hour")) or 0,
               m.group("minute") and int(m.group("minute")) or 0,
               m.group("second") and int(m.group("second")) or 0)

      tstamp = None
      dtime = None
      try:
         tstamp = datetime.time(*date[3:len(date)])
      except ValueError:
         ##Don't create timestamps by default
         pass
         
      try:
         dtime = datetime.date(*date[0:3])
      except ValueError:
         dtime = datetime.date.today()
         
      if tstamp:
         ###
         # Combine the date and timestamp into a datetime type
         ###
         dt = datetime.datetime.combine( dtime, tstamp )
      else:
         dt = dtime

   return dt

def _build_new_rep(nfields, col_prefixes):

   rep = ""
   if nfields:
      ##Build all named into a where clause fields##
      for field in NAMED_FIELDS:
         if (field == 'start_date') or (field == 'end_date'):
            continue
         if (field in nfields) and (field in col_prefixes):
            if field == 'socorro_id':
               rep += " AND %s.%s=%s " % (col_prefixes[field], field, int(nfields[field]))
            else: 
               if (nfields[field][0] == '%') or (nfields[field][ len( nfields[field] )-1 ] == '%'): 
                  rep += " AND %s.%s LIKE '%s' " % (col_prefixes[field], field, nfields[field])
               else:
                  rep += " AND %s.%s='%s' " % (col_prefixes[field], field, nfields[field])

   return rep

def _set_dates_for_placeholders(nfields):

   ##Handle null fields##
   start, end = _get_date_range()
   if ('start_date' not in nfields) or (nfields['start_date'] == ''):
      nfields['start_date'] = str(start)
   if ('end_date' not in nfields) or (nfields['end_date'] == ''):
      nfields['end_date'] = str(end)

   ##utf-8 encode and Parse date and time##
   start_date = _get_datetime_from_string( nfields['start_date'].encode('utf-8') )
   end_date = _get_datetime_from_string( nfields['end_date'].encode('utf-8') )

   start_type = type(start_date)
   end_type = type(end_date)

   if start_type != end_type:
      ####
      #Find which one is not datetime and convert it
      #so we can compute a timedelta without a type 
      #error
      ####
      dt_type = type(datetime.datetime.today())
      if start_type != dt_type:
         start_date = datetime.datetime.combine( start_date, datetime.time(0, 0, 0) )
      elif end_type != dt_type:
         end_date = datetime.datetime.combine( end_date, datetime.time(0, 0, 0) )

   ##Measure the difference in days##
   time_difference = end_date - start_date

   ##Maximum date range allowed in days##
   max_difference = datetime.timedelta(days=60)

   ####
   # if the maximum date range is exceeded, use the start date
   # provided to calculate an end date within max_difference.
   #####
   if time_difference > max_difference: 
      end_days = start_date + max_difference
      end_date = str(end_days)

   nfields['start_date'] = str(start_date)
   nfields['end_date'] = str(end_date)

def _get_json(nfields, col_prefixes, path):

   _set_dates_for_placeholders(nfields)

   rep = _build_new_rep(nfields, col_prefixes)

   data = settings.DHUB.execute(proc=path,
                                debug_show=settings.DEBUG,
                                replace=[ nfields['start_date'], nfields['end_date'], rep ],
                                return_type='table')

   return simplejson.dumps( {'columns':data['columns'], 
                             'data':data['data'], 
                             'start_date':nfields['start_date'], 
                             'end_date':nfields['end_date']} )

####
#VIEW_ADAPTERS maps view names to function
#references that handle them.  All adapters
#need to return json
####
VIEW_ADAPTERS = dict( crashes_st=_get_crashes_st,
                      crash_urls_st=_get_crash_urls_st,
                      crash_detail_st=_get_crash_detail_st,

                      assertions_st=_get_assertions_st,
                      assertion_urls_st=_get_assertion_urls_st,
                      assertion_detail_st=_get_assertion_detail_st,

                      crashes_ut=_get_crashes_ut,
                      assertions_ut=_get_assertions_ut,
                      assertion_urls_ut=_get_assertion_urls_ut,
                      assertion_detail_ut=_get_assertion_detail_ut,

                      valgrinds_ut=_get_valgrinds_ut,
                      valgrind_urls_ut=_get_valgrind_urls_ut,
                      valgrind_detail_ut=_get_valgrind_detail_ut,

                      socorro_record=_get_socorro_record,

                      resubmission_urls_ud=_get_resubmission_urls,
                      all_resubmission_urls_ud=_get_all_resubmission_urls
                      )

NAMED_FIELDS = set( ['signature',
                     'url',
                     'fatal_message',
                     'start_date',
                     'end_date',
                     'new_signatures',
                     'socorro_id',
                     'address',
                     'pluginfilename',
                     'pluginversion',
                     'exploitability',
                     'assertion',
                     'location',
                     'message'] )

VIEW_PAGES = set([ 'bhview', 'get_help' ])



