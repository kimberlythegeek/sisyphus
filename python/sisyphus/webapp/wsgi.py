import os
import sys

from django.core.wsgi import get_wsgi_application

try:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    sisyphus_dir     = os.environ["SISYPHUS_DIR"]
    tempdir          = os.path.join(sisyphus_dir, 'python')
    if tempdir not in sys.path:
        sys.path.append(tempdir)

    tempdir          = os.path.join(tempdir, 'sisyphus')
    if tempdir not in sys.path:
        sys.path.append(tempdir)

    tempdir          = os.path.join(tempdir, 'webapp')
    if tempdir not in sys.path:
        sys.path.append(tempdir)

except Exception, e:
    sys.stderr.write('bughunter error wsgi.py: %s\n' % e)
    raise

_application = None

def application(env, start_response):
    global _application

    if not _application:
        _application = get_wsgi_application()

    return _application(env, start_response)


