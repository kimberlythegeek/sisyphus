# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import os
import re
import signal
import subprocess
import sys
import traceback
import urllib
import urllib2
import urlparse

import taskcluster


def makeUnicodeString(s):
    # http://farmdev.com/talks/unicode/
    if isinstance(s, basestring):
        if not isinstance(s, unicode):
            s = unicode(s, "utf-8", errors='replace')
    return s

# Return a string containing the formatted exception message.
# If an error occurs, such as a MemoryError, return a simple
# message.
def formatException():
    etype, evalue, etraceback = sys.exc_info()

    try:
        return etype, evalue, ''.join(traceback.format_exception(etype, evalue, etraceback))
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        return None, None, "Error in formatException"

def getTimestamp(hiresolution=False):
    timestamp = datetime.datetime.now()
    datetimestamp = datetime.datetime.strftime(timestamp, "%Y-%m-%dT%H:%M:%S")
    if hiresolution:
        datetimestamp = "%s.%06d" % (datetimestamp, timestamp.microsecond)
    return datetimestamp

def convertTimestamp(s):
    try:
        s = re.sub('\.[0-9]*$', '', s)
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        pass

    return datetime.datetime.strptime('2009-01-1T00:00:00', "%Y-%m-%dT%H:%M:%S")

def convertTimeToString(timestamp, hiresolution=False):
    datetimestamp = datetime.datetime.strftime(timestamp, "%Y-%m-%dT%H:%M:%S")
    if hiresolution:
        datetimestamp = "%s.%06d" % (datetimestamp, timestamp.microsecond)
    return datetimestamp

# getSignalName cribbed from timed_run.py by Jesse Ruderman
def getSignalName(num):
    for p in dir(signal):
        if p.startswith("SIG") and not p.startswith("SIG_"):
            if getattr(signal, p) == num:
                return p
    return "UNKNOWN"

def convertReturnCodeToExitStatusMessage(rc):
    exitstatusmessage = ""

    if not isinstance(rc, int):
        exitstatusmessage = "None"

    elif os.WIFSIGNALED(rc):
        signum = os.WTERMSIG(rc)
        exitstatusmessage = "signal %d %s" % (signum, getSignalName(signum))

    elif os.WIFEXITED(rc):
        exitstatus = os.WEXITSTATUS(rc)
        if exitstatus == 0:
            exitstatusmessage = 'NORMAL'
        else:
            exitstatusmessage = 'ABNORMAL ' + str(exitstatus)

    if isinstance(rc, int) and os.WCOREDUMP(rc):
        exitstatusmessage += " dumped core"

    return exitstatusmessage.strip()

def timedReadLine_handler(signum, frame):
    print 'timedReadLine timeout'
    raise IOError('ReadLineTimeout')

def timedReadLine(filehandle, timeout = None):
    """
    Attempt to readline from filehandle. If readline does not return
    within timeout seconds, raise IOError('ReadLineTimeout')
    """

    if timeout is None:
        timeout = 300

    default_alarm_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, timedReadLine_handler)
    signal.alarm(timeout)

    try:
        line = filehandle.readline()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, default_alarm_handler)

    return line

def encodeUrl(url):
    # encode the url.
    # Unquote the url to replace %dd encoded characters with
    # their raw values, then encode the result. This will help
    # protect against unsafe characters as well as prevent
    # encoding already encoded characters.

    url            = makeUnicodeString(urllib.unquote(url))
    urlParseObject = urlparse.urlparse(url)
    urlPieces      = [urllib.quote(urlpiece.encode('utf-8'), "/=:&;") for urlpiece in urlParseObject]
    url            = urlparse.urlunparse(urlPieces)
    return url

def downloadFile(url, destination, credentials = None, timeout = None):
    """
    Download the file at url to destination using curl. Return true if
    successful, false otherwise.

     curl options
     -f output non-zero exit code when fail to download.
     -S show error if failure
     -s silent mode
     -L follow 3XX redirections
     -m timeout
     --create-dirs create path if needed

    """

    if url is None or destination is None:
        raise Exception('downloadFileArguments')

    cmd = ['curl', '-LsSf', '--create-dirs', '-o', destination]

    if timeout is not None:
        cmd.extend(['-m', timeout])
    if credentials is not None:
        cmd.extend(['-u', credentials])

    cmd.append(encodeUrl(url))

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    stdout = proc.communicate()[0]

    if proc.returncode != 0:
        sys.stdout.write(stdout)
    return proc.returncode == 0

def openFileDescriptorCount():

    count = 0

    for fd in xrange(0x10000):
        try:
            os.fstat(fd)
            count += 1
        except OSError:
            pass

    return count

def closeFileDescriptors(fd_start, fd_end):

    # Close file descriptors from fd_start inclusive to fd_end
    # exclusive. This is equivalent to os.closerange in Python 2.6

    for fd in xrange(fd_start, fd_end):
        try:
            os.close(fd)
        except OSError:
            pass

def crash_report_field2int(s):
    """
    Convert a string from a crash report which represents an integer field
    to an int if possible, otherwise return None
    """

    try:
        return int(s)
    except ValueError:
        return None


def crash_report_field2string(s, prefix = None):
    """
    Convert a string from a crash report which represents a string field
    as follows:

    \N        return None
    [blank]   return ''
    otherwise return the string with the prefix stripped.
    """

    if s == '\\N':
        return None

    if s == '[blank]':
        return ''

    if prefix and prefix == s[:len(prefix)]:
        return s[len(prefix):]

    return s


from django.db import connection

outstandingLocks = {}

def getLock(name, timeout = 300):
    cursor    = connection.cursor()
    cursor.execute("SELECT GET_LOCK(%s, %s) AS RESULT", [name, timeout])

    if cursor.fetchone()[0] != 1:
        return False

    outstandingLocks[name] = datetime.datetime.now()
    return True

def releaseLock(name):

    cursor = connection.cursor()
    cursor.execute("SELECT RELEASE_LOCK(%s)", [name])

    lockDuration = datetime.datetime.now() - outstandingLocks[name]
    del outstandingLocks[name]

    return lockDuration


from django.contrib.auth.models import User

def get_django_user_id(username, email):
    """Lookup the id associated with the username
    """
    user_objects = User.objects.all()
    user_id = 0
    for u in user_objects:
      if username == u.username or username == u.email:
         user_id = u.id
         break
    return user_id

# http://atlee.ca/software/poster/index.html
import poster

# Register the streaming http handlers with urllib2
opener = poster.streaminghttp.register_openers()
opener.add_handler(urllib2.ProxyHandler({}))

import gzip

class FileUploader(object):
    def __init__(self, post_files_url, model_name, dest_row, dest_key, dest_path):
        self.post_files_url = post_files_url
        self.model_name = model_name
        self.dest_row = dest_row
        self.dest_key = dest_key
        self.multipart_param_list = []
        self.filedict_list = []
        self.multipart_param_list.append( ('pk',         dest_key) )
        self.multipart_param_list.append( ('model_name', model_name) )
        self.multipart_param_list.append( ('dest_path',  dest_path) )

    def add(self, dest_field, dest_file, src_file, compress=False, remove=True):
        if not os.path.exists(src_file):
            raise Exception('FileUploader.DoesNotExist')

        self.filedict_list.append({ "file": src_file, "remove": remove})
        if compress:
            compressed_src_file = src_file + '.gz'
            self.filedict_list.append({ "file": compressed_src_file, "remove": True})
            fin = open(src_file, 'rb')
            fout = gzip.open(compressed_src_file, 'wb')
            while True:
                data = fin.read(0x1000)
                if not data:
                    break
                fout.write(data)
            fin.close()
            fout.close()
            src_file = compressed_src_file
            dest_file += '.gz'

        self.multipart_param_list.append(poster.encode.MultipartParam.from_file(dest_field, src_file))
        self.multipart_param_list[-1].filename = dest_file

    def send(self):

        datagen, headers = poster.encode.multipart_encode(self.multipart_param_list)
        request = urllib2.Request(self.post_files_url, datagen, headers)
        try:
            # save the current state of the dest_row since the file upload
            # will modify it.
            self.dest_row.save()
            result = urllib2.urlopen(request)
            result.close()
        except (KeyboardInterrupt, SystemExit):
            raise
        except urllib2.HTTPError:
            raise
        except urllib2.URLError:
            raise
        finally:
            # have to reload the row to pick up the updated file paths
            # row.__class__ is the Django model for the table the row lives in.
            self.dest_row = self.dest_row.__class__.objects.get(pk = self.dest_key)

        for filedict in self.filedict_list:
            if filedict["remove"]:
                os.unlink(filedict["file"])

        # return the modified row from the database
        return self.dest_row


def mungeUnicodeToUtf8(string):
    # Match long utf-8 encodings of unicode characters and replace them with
    # the value \uFFFD
    # http://dev.mysql.com/doc/refman/5.1/en/charset-unicode-utf8.html
    # MySQL 5.1 only supports 3-byte utf-8.
    # http://stackoverflow.com/questions/3220031/how-to-filter-or-replace-unicode-characters-that-would-take-more-than-3-bytes-i
    reUtf8Unicode = re.compile(u'[^\u0000-\uD7FF\uE000-\uFFFF]', re.UNICODE)
    return reUtf8Unicode.sub(u'\uFFFD', string)


# Taskcluster related utilities

def parse_namespace(namespace):
    os_map = {
        'linux': {'os_name': 'Linux', 'bits': '32'},
        'linux64': {'os_name': 'Linux', 'bits': '64'},
        'win32': {'os_name': 'Windows NT', 'bits': '32'},
        'win64': {'os_name': 'Windows NT', 'bits': '64'},
        'macosx64': {'os_name': 'Mac OS X', 'bits': '64'},
    }

    platform_parts = namespace.split('.')[-1].split('-')
    platform = platform_parts[0]
    if platform not in os_map:
        return None
    os_data = os_map[platform]
    build_type = platform_parts[-1]
    os_data['build_type'] = build_type
    build_type_extra = ''
    if len(platform_parts) >= 3:
        build_type_extra = '-'.join(platform_parts[1:-1])
    os_data['extra'] = build_type_extra
    return os_data


def get_artifacts(task_id, run_id):
    queue = taskcluster.queue.Queue()
    response = queue.listArtifacts(task_id, run_id)
    while True:
        if 'artifacts' not in response:
            raise StopIteration
        artifacts = response['artifacts']
        for artifact in artifacts:
            yield artifact
        if 'continuationToken' not in response:
            raise StopIteration
        response = queue.listArtifacts(task_id, run_id, {
            'continuationToken': response['continationToken']})


def find_latest_task_id(repo, os_name, bits, build_type, build_type_extra, log=None):
    """Return the task id for the latest build for the
    matching platforms and build types or None if not found.
    """

    if log:
        log('find_latest_task_id: repo: %s, os_name: %s, bits: %s, build_type: %s, build_type_extra: %s' %
            (repo, os_name, bits, build_type, build_type_extra))

    namespace = 'gecko.v2.%s.latest.firefox' % repo
    payload = {}
    index = taskcluster.index.Index()
    response = index.listTasks(namespace, payload)

    if log:
        log('find_latest_task_id: listTasks(%s, %s): response: %s' %
            (namespace, payload, response))

    for task in response['tasks']:
        if log:
            log('find_latest_task_id: task: %s' % task)
        task_id = task['taskId']
        task_namespace = task['namespace']
        os_data = parse_namespace(task_namespace)
        if log:
            log('find_latest_task_id: os_data: %s' % os_data)
        if not os_data:
            continue
        if os_name == os_data['os_name'] and \
           bits == os_data['bits'] and \
           build_type == os_data['build_type'] and \
           build_type_extra == os_data['extra']:
            if log:
                log('find_latest_task_id: found task_id: %s' % task_id)
            return task_id
    return None


def find_build_by_task_id(task_id, re_build, log=None):
    """Return url to build for the specified task.
    """
    if task_id is None:
        if log:
            log('find_build_by_task: task_id is None')
        return None
    queue = taskcluster.queue.Queue()
    status = queue.status(task_id)['status']
    if log:
        log('find_build_by_task_id: status: %s' % status)
    for run in reversed(status['runs']): # runs
        if run['state'] != 'completed':
            continue
        run_id = run['runId']
        artifacts = get_artifacts(task_id, run_id)
        try:
            build_url = None
            while not build_url:
                artifact = artifacts.next()
                artifact_name = artifact['name']
                if log:
                    log('find_build_by_task_id: artifact: %s' % artifact)
                search = re_build.search(artifact_name)
                if search:
                    url_format = 'https://queue.taskcluster.net/v1/task/%s/runs/%s/artifacts/%s'
                    build_url = url_format % (task_id, run_id, artifact_name)
                    return build_url
        except StopIteration:
            pass
    return None


def reloadProgram(program_info):
        newargv = sys.argv
        newargv.insert(0, sys.executable)
        os.chdir(program_info.startdir)

        # set all open file handlers to close on exec.
        # use 64K as the limit to check as that is the max
        # on Windows XP. The performance issue of doing this
        # is negligible since it is only run during a program
        # reload.
        from fcntl import fcntl, F_GETFD, F_SETFD, FD_CLOEXEC
        for fd in xrange(0x3, 0x10000):
            try:
                fcntl(fd, F_SETFD, fcntl(fd, F_GETFD) | FD_CLOEXEC)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                pass

        os.execvp(sys.executable, newargv)
