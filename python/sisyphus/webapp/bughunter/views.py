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

from sisyphus.webapp.bughunter import models
from sisyphus.webapp import settings
from sisyphus.automation import utils

APP_JS = 'application/json'

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

    last_hour_timestamp = utils.convertTimeToString(datetime.datetime.now() - datetime.timedelta(hours=1))


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
    response['Sisyphus-Localtime'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
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

    if request.method != 'POST':
        # http://docs.djangoproject.com/en/1.2/ref/request-response/#django.http.HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])

    try:
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
                        viewslog = open('/tmp/views.log', 'ab+')
                        viewslog.write("creating %s\n" % dest_dir)
                        os.mkdir(dest_dir)
                        viewslog.write("created %s\n" % dest_dir)
                        viewslog.close()
        if not request.FILES:
            error_list.append('Missing file content')

        if error_list:
            viewslog = open('/tmp/views.log', 'ab+')
            viewslog.write('Bad Request: %s.\n' % ','.join(error_list))
            viewslog.close()
            return HttpResponseBadRequest('Bad Request: %s.' % ','.join(error_list))

        try:
            row = model.objects.get(pk = pk)
        except model.DoesNotExist:
            return httpResponseNotFound('%s %s not found' % (model_name, pk))

        #http://docs.djangoproject.com/en/1.2/ref/request-response/#django.http.HttpRequest.FILES

        rfile = re.compile(r'^[\w,.-]*$')

        viewslog = open('/tmp/views.log', 'ab+')
        for fieldname, uploadedfile in request.FILES.items():

            filename    = uploadedfile.name
            viewslog.write("%s: fieldname: %s, filename: %s\n" % (datetime.datetime.now().isoformat(), fieldname, filename))

            if not rfile.match(filename):
                return HttpResponseBadRequest('Bad Request: filename %s' % filename)

            oldfilepath = eval('row.' + fieldname)
            viewslog.write("%s: oldfilepath: %s\n" % (datetime.datetime.now().isoformat(), oldfilepath))
            newfilepath = os.path.join(dest_dir, filename).encode('utf-8')
            viewslog.write("%s: newfilepath: %s\n" % (datetime.datetime.now().isoformat(), newfilepath))

            if oldfilepath:
                # If the current field value points to an existing file, unlink it.
                # We must do this prior to writing the new file since the old and
                # new may have the same file names.
                viewslog.write("%s: checking oldfilepath: %s\n" % (datetime.datetime.now().isoformat(), oldfilepath))
                if os.path.exists(oldfilepath):
                    viewslog.write("%s: unlinking oldfilepath: %s\n" % (datetime.datetime.now().isoformat(), oldfilepath))
                    os.unlink(oldfilepath)

            row.__setattr__(fieldname, newfilepath)

            output = open(newfilepath, 'wb+')

            for chunk in uploadedfile.chunks():
                output.write(chunk)

            output.close()

        viewslog.close()
        row.save()
        response = HttpResponseRedirect('/bughunter/media/')

    except:
        exceptionType, exceptionValue, errorMessage  = utils.formatException()
        viewslog = open('/tmp/views.log', 'wb+')
        viewslog.write("%s: %s" % (datetime.datetime.now().isoformat(), errorMessage))
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
        
