from django.contrib import admin

from sisyphus.webapp.bughunter.models import Worker
admin.site.register(Worker)

from sisyphus.webapp.bughunter.models import Branch
admin.site.register(Branch)

from sisyphus.webapp.bughunter.models import Build
admin.site.register(Build)

from sisyphus.webapp.bughunter.models import Crash
admin.site.register(Crash)

from sisyphus.webapp.bughunter.models import Assertion
admin.site.register(Assertion)

from sisyphus.webapp.bughunter.models import Valgrind
admin.site.register(Valgrind)

from sisyphus.webapp.bughunter.models import UnitTestRun
admin.site.register(UnitTestRun)

from sisyphus.webapp.bughunter.models import UnitTestResult
admin.site.register(UnitTestResult)

from sisyphus.webapp.bughunter.models import UnitTestCrash
admin.site.register(UnitTestCrash)

from sisyphus.webapp.bughunter.models import UnitTestCrashDumpMetaData
admin.site.register(UnitTestCrashDumpMetaData)

from sisyphus.webapp.bughunter.models import UnitTestAssertion
admin.site.register(UnitTestAssertion)

from sisyphus.webapp.bughunter.models import UnitTestValgrind
admin.site.register(UnitTestValgrind)

from sisyphus.webapp.bughunter.models import SocorroRecord
admin.site.register(SocorroRecord)

from sisyphus.webapp.bughunter.models import SiteTestRun
admin.site.register(SiteTestRun)

from sisyphus.webapp.bughunter.models import SiteTestCrash
admin.site.register(SiteTestCrash)

from sisyphus.webapp.bughunter.models import SiteTestCrashDumpMetaData
admin.site.register(SiteTestCrashDumpMetaData)

from sisyphus.webapp.bughunter.models import SiteTestAssertion
admin.site.register(SiteTestAssertion)

from sisyphus.webapp.bughunter.models import SiteTestValgrind
admin.site.register(SiteTestValgrind)

