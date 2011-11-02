# Django settings for sisyphus.webapp project.

import os
from datasource.bases.BaseHub import BaseHub
from datasource.hubs.MySQL import MySQL

from bughunter.filters.templatetags.bh_unorderedlist import bh_unorderedlist

# Set Database connectivity via environment
SISYPHUS_DATABASE          = os.environ["SISYPHUS_DATABASE"]
SISYPHUS_DATABASE_USER     = os.environ["SISYPHUS_DATABASE_USER"]
SISYPHUS_DATABASE_PASSWORD = os.environ["SISYPHUS_DATABASE_PASSWORD"]
SISYPHUS_DATABASE_HOST     = os.environ["SISYPHUS_DATABASE_HOST"]
SISYPHUS_DATABASE_PORT     = os.environ["SISYPHUS_DATABASE_PORT"]

# Set Sisyphus URL via the environment
SISYPHUS_URL               = os.environ["SISYPHUS_URL"]

# from jgriffin's settings.py for templates
ROOT = os.path.dirname(os.path.abspath(__file__))
path = lambda *a: os.path.join(ROOT, *a)

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
  ('bclary', 'bob@bclary.com'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE'   : 'django.db.backends.mysql', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME'     : SISYPHUS_DATABASE,          # Or path to database file if using sqlite3.
        'USER'     : SISYPHUS_DATABASE_USER,     # Not used with sqlite3.
        'PASSWORD' : SISYPHUS_DATABASE_PASSWORD, # Not used with sqlite3.
        'HOST'     : SISYPHUS_DATABASE_HOST,     # Set to empty string for localhost. Not used with sqlite3.
        'PORT'     : SISYPHUS_DATABASE_PORT,     # Set to empty string for default. Not used with sqlite3.
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = path('media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = SISYPHUS_URL + '/media/'

#Login/logout locations for views
VIEW_LOGOUT = '/bughunter/logout/'
VIEW_LOGIN_PAGE = '/bughunter/login/'
VIEW_LANDING_PAGE = '/bughunter/views/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/djangoadmin/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = os.environ["SISYPHUS_DJANGO_SECRET_KEY"]

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'sisyphus.webapp.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    path('templates')
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.admindocs',

    ##Bughunter related apps##
    'bughunter',
    'bughunter.filters',
)

SERIALIZATION_MODULES = {
    'json': 'wadofstuff.django.serializers.json'
}

AUTHENTICATION_BACKENDS = [
    'auth.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

try:
    import ldap
    from django_auth_ldap.config import LDAPSearch, GroupOfNamesType
except ImportError:
    pass
else:
    AUTHENTICATION_BACKENDS.insert(1, 'auth.backends.MozillaLDAPBackend')

    AUTH_LDAP_SERVER_URI = os.environ['SISYPHUS_LDAP_SERVER_URI']
    AUTH_LDAP_BIND_DN = os.environ['SISYPHUS_LDAP_BIND_DN']
    AUTH_LDAP_BIND_PASSWORD = os.environ['SISYPHUS_LDAP_BIND_PASSWORD']

    AUTH_LDAP_USER_ATTR_MAP = {
        "first_name": "givenName",
        "last_name": "sn",
        "email": "mail",
    }

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        "dc=mozilla",
        ldap.SCOPE_SUBTREE,
        "mail=%(user)s"
    )

    AUTH_LDAP_GROUP_SEARCH = LDAPSearch("ou=groups,dc=mozilla",
        ldap.SCOPE_SUBTREE, "(objectClass=groupOfNames)"
    )
    AUTH_LDAP_GROUP_TYPE = GroupOfNamesType()
    #AUTH_LDAP_REQUIRE_GROUP = os.environ['SISYPHUS_LDAP_RESTRICTED_GROUP']

# Import local settings to add to/override the above
try:
    from local_settings import *
except ImportError:
    pass

####
#Configuration of datasource hub:
#	1 Build the datasource struct
# 	2 Add it to the BaseHub
#	3 Instantiate a MySQL hub
####
dataSource = { SISYPHUS_DATABASE : { "hub":"MySQL",
                                     "master_host":{"host":SISYPHUS_DATABASE_HOST,
                                                    "user":SISYPHUS_DATABASE_USER,
                                                    "passwd":SISYPHUS_DATABASE_PASSWORD},
                                                    "default_db":SISYPHUS_DATABASE,
                                     "procs": ["%s%s" % (ROOT, "/procs/bughunter.json")]
              }
}
BaseHub.addDataSource(dataSource)
DHUB = MySQL(SISYPHUS_DATABASE)
