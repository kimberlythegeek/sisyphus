import os
import sys
import re
import datetime

from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect, HttpResponseServerError, HttpResponseBadRequest
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt

from sisyphus.webapp.bughunter import models
from sisyphus.webapp import settings
from sisyphus.automation import utils

def crashtests(request):
    return render_to_response('bughunter.crashtests.html', {})

def unittests(request):
    return render_to_response('bughunter.unittests.html', {})

def home(request):
    return render_to_response('bughunter.index.html', {})

def admin(request):
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
        worker_data_list.append({'worker_key'       : worker_key,
                                 'builder_active'   : worker_data[worker_key]['builder']['active'],
                                 'builder_total'    : worker_data[worker_key]['builder']['total'],
                                 'crashtest_active' : worker_data[worker_key]['crashtest']['active'],
                                 'crashtest_total'  : worker_data[worker_key]['crashtest']['total'],
                                 'crashtest_jobs'   : worker_data[worker_key]['crashtest']['jobs'],
                                 'unittest_active'  : worker_data[worker_key]['unittest']['active'],
                                 'unittest_total'   : worker_data[worker_key]['unittest']['total'],
                                 'unittest_jobs'    : worker_data[worker_key]['unittest']['jobs'],
                                 })

    worker_data_list.sort( cmp=lambda x, y: cmp(x['worker_key'], y['worker_key'] ))
    return render_to_response('bughunter.admin.html', {'worker_data_list' : worker_data_list})

def workers(request):
    worker_rows = models.Worker.objects.order_by('hostname').all()

    return render_to_response('bughunter.workers.html', {'worker_rows' : worker_rows})

def worker_log(request, worker_id):
    worker_row = models.Worker.objects.get(pk = worker_id)
    log_rows = models.Log.objects.filter(worker__id__exact=worker_id).order_by('datetime').all()

    return render_to_response('bughunter.worker_log.html', {'worker_row' : worker_row, 'log_rows' : log_rows})

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
