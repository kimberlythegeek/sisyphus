from django.db import models
from django.forms import ModelForm

# See http://docs.djangoproject.com/en/1.2/topics/forms/modelforms/

class AbstractWorker(models.Model):
    """ An abstract base class containing the defining information for
    the class of worker. """
    os_name           = models.CharField(max_length=10, db_index=True) # Linux, Windows NT, Mac OS X, ...
    os_version        = models.CharField(max_length=10, db_index=True) # 5.1, 10.5.8, ...
    cpu_name          = models.CharField(max_length=16, db_index=True) # x86, x86_64, amd32, amd64, ...
    build_cpu_name    = models.CharField(max_length=16, null = True, blank = True, db_index=True) # For cases like our Windows 7 machines where we can have 32bit builds running on 64bit vms.

    class Meta:
        abstract = True

class Worker(AbstractWorker):
    """ An abstract base class that encapsulates the information related to a worker."""

    hostname          = models.CharField(max_length=64, db_index=True)
    datetime          = models.DateTimeField(auto_now=True)
    state             = models.CharField(max_length=10, db_index=True)
    worker_type       = models.CharField(max_length=16, db_index=True)
    buildspecs        = models.CharField(max_length=255, null = False, blank = True)

    def __unicode__(self):
        return self.hostname

    class Meta:
        db_table = 'Worker'
        ordering = ['hostname']

class WorkerForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = Worker

class Log(models.Model):
    datetime          = models.DateTimeField(auto_now=True)
    worker            = models.ForeignKey(Worker)
    message           = models.TextField()

    class Meta:
        db_table = 'Log'
        ordering = ['datetime']

class AbstractProduct(AbstractWorker):
    """ An abstract base class containing common product information
    related to the building or execution of the product on a
    particular class of machine. """
    product           = models.CharField(max_length=16, db_index=True) # Firefox, ...
    branch            = models.CharField(max_length=16, db_index=True) # Gecko branch: 1.9.2, 2.0.0, ...
    buildtype         = models.CharField(max_length=32, db_index=True)  # opt, debug, nightly/release

    class Meta:
        abstract = True

class Branch(models.Model):
    """ A class that lists the supported Gecko branches and their
    mapping to Firefox versions."""

    product           = models.CharField(max_length=16)
    branch            = models.CharField(max_length=16)
    major_version     = models.CharField(max_length=16)
    buildtype         = models.CharField(max_length=32)

    def __unicode__(self):
        return '%s/%s' % (self.product, self.branch)

    class Meta:
        db_table = 'Branch'

class BranchForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = Branch

class Build(AbstractProduct):
    """ A class that contains meta data about and "links" to product
    builds that have been uploaded to the database. """

    build_id           = models.CharField(max_length=255, primary_key = True) # CouchDB: <product>_<branch>_<buildtype>_<os_name>_<cpu_name>
    builddate          = models.DateTimeField(null = True)
    changeset          = models.CharField(max_length=16, null = True, blank = True)
    worker             = models.ForeignKey(Worker) # CouchDB change: couchdb field is worker_id, but use django style for foreign key names
    buildavailable     = models.NullBooleanField()
    state              = models.CharField(max_length=64)
    datetime           = models.DateTimeField(auto_now=True)
    buildsuccess       = models.NullBooleanField()
    packagesuccess     = models.NullBooleanField()
    clobbersuccess     = models.NullBooleanField()
    uploadsuccess      = models.NullBooleanField()
    executablepath     = models.CharField(max_length=256, null = True, blank =True) # XXX: length?
    product_package    = models.CharField(max_length = 256, null = True, blank = True)
    symbols_file       = models.CharField(max_length = 256, null = True, blank = True)
    tests_file         = models.CharField(max_length = 256, null = True, blank = True)
    package_log        = models.CharField(max_length = 256, null = True, blank = True)
    checkout_log       = models.CharField(max_length = 256, null = True, blank = True)
    build_log          = models.CharField(max_length = 256, null = True, blank = True)
    clobber_log        = models.CharField(max_length = 256, null = True, blank = True)

    def __unicode__(self):
        return self.build_id

    class Meta:
        db_table = 'Build'

class BuildForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = Build

class Crash(AbstractProduct):
    """
    A class to represent the crashes for a worker class. When new
    crashes are detected, a row is inserted into the Crash table, and
    the individual UnitTestCrash and SiteTestCrash are created to link
    back to it.

    Crash serves as a "header" for the SiteTestCrash and UnitTestCrash
    classes and as such should not contain information which may be
    too specific to a individual crash. It groups crashes by the
    product, branch, build type, operating system, cpu, signature and
    message. It may represent several distinct bugs.

    SiteTestCrash and UnitTestCrash inherit from
    AbstractCrash. AbstractCrash contains the common crash instance
    specific information.
    """

    signature         = models.CharField(max_length=3000, null = True, blank = True)
    bugs              = models.CharField(max_length=3000, null = True, blank = True) # comma delimited list of bug numbers

    def __unicode__(self):
        return '%s %s %s' % (self.reason, self.address, self.crash)

    class Meta:
        db_table = 'Crash'

class CrashForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = Crash

class AbstractCrash(models.Model): #AbstractCrash(AbstractProduct):
    """ An abstract base class to represent the common fields of an
    actual crash during a test."""

    url               = models.CharField(max_length=1000, db_index=True)
    datetime          = models.DateTimeField(auto_now=True)
    minidump          = models.CharField(max_length=256, null = True, blank = True) # breakpad minidump
    extradump         = models.CharField(max_length=256, null = True, blank = True)
    msdump            = models.CharField(max_length=256, null = True, blank = True) # optional (new) ms dump file
    reason            = models.CharField(max_length=64, null = True, blank = True)
    address           = models.CharField(max_length=32, null = True, blank = True)
    crashreport       = models.CharField(max_length=256, null = True, blank = True)
    crashtype         = models.CharField(max_length=8, null = True, blank = True, db_index=True) # browser, plugin, ...?
    pluginfilename    = models.CharField(max_length=64, null = True, blank = True, db_index=True) # flash, etc.
    pluginversion     = models.CharField(max_length=64, null = True, blank = True, db_index=True)
    exploitability    = models.CharField(max_length=11, null = True, blank = True, db_index=True)

    class Meta:
        abstract = True

class Assertion(AbstractProduct):
    """
    A class to represent the ASSERTIONs for a worker class. When new
    ASSERTIONs are detected, a row is inserted into the Assertion
    table, and the individual UnitTestAssertion and SiteTestAssertion
    are created to link back to it.

    Assertion serves as a "header" for the SiteTestAssertion and
    UnitTestAssertion classes and as such should not contain
    information which may be too specific to a individual
    ASSERTION. It groups ASSERTIONs by the product, branch, build
    type, operating system, cpu, signature and message. It may
    represent several distinct bugs.

    SiteTestAssertion and UnitTestAssertion inherit from
    AbstractAssertion. AbstractAssertion contains the common ASSERTION
    instance specific information.
    """

    assertion         = models.CharField(max_length=512, db_index=True)
    location          = models.CharField(max_length=512, db_index=True)

    def __unicode__(self):
        return self.assertion

    class Meta:
        db_table = 'Assertion'

class AssertionForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = Assertion

class AbstractAssertion(models.Model): #AbstractAssertion(AbstractProduct):
    """ An abstract base class to represent the common fields of an
    actual assertion during a test."""

    url               = models.CharField(null = True, max_length=1000, db_index=True)
    datetime          = models.DateTimeField(auto_now=True)
    stack             = models.TextField(null = True, blank = True) # New field. 256 is too small, but I don't know what to use yet.
    count             = models.IntegerField(null = True)

    class Meta:
        abstract = True

class Valgrind(AbstractProduct):
    """
    A class to represent the valgrind messages for a worker
    class. When new valgrind are detected, a row is inserted into the
    Valgrind table, and the individual UnitTestValgrind and
    SiteTestValgrind are created to link back to it.

    Valgrind serves as a "header" for the SiteTestValgrind and
    UnitTestValgrind classes and as such should not contain
    information which may be too specific to a individual valgrind. It
    groups valgrinds by the product, branch, build type, operating
    system, cpu, signature and message. It may represent several
    distinct bugs.

    SiteTestValgrind and UnitTestValgrind inherit from
    AbstractValgrind. AbstractValgrind contains the common valgrind
    instance specific information.
    """

    signature         = models.TextField() # This is a combination of the valgrind message plus the  processed version of the first line of valgrind data which is not a pure address and which has all non-identifier type chars stripped.
    message           = models.CharField(max_length=256, db_index=True) # Invalid read, etc.

    def __unicode__(self):
        return self.valgrind

    class Meta:
        db_table = 'Valgrind'

class ValgrindForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = Valgrind

class AbstractValgrind(models.Model): #AbstractValgrind(AbstractProduct):
    """ An abstract base class to represent the common fields of an
    actual valgrind message during a test."""

    url               = models.CharField(max_length=1000, db_index=True)
    datetime          = models.DateTimeField(auto_now=True)
    stack             = models.TextField() # CouchDB: This is a block of text with newlines and raw addresses that contains the valgrind message/stack.
    count             = models.IntegerField()

    class Meta:
        abstract = True


class AbstractCrashDumpMetaData(models.Model):
    """ An abstract base class which contains the meta data from the
    dump's extra file as key/value pairs."""

    key               = models.CharField(max_length=32, db_index=True)
    value             = models.TextField(max_length=2048)

    class Meta:
        abstract = True

class UnitTestBranch(models.Model):
    branch            = models.CharField(max_length=16)
    test              = models.CharField(max_length=32)

    def __unicode__(self):
        return '%s %s' % (self.branch, self.test)

    class Meta:
        db_table = 'UnitTestBranch'

class UnitTestBranchForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = UnitTestBranch

class UnitTestRun(AbstractProduct):
    worker            = models.ForeignKey(Worker, null = True, blank = True)
    unittestbranch    = models.ForeignKey(UnitTestBranch, null = True, blank = True)
    changeset         = models.CharField(max_length=16, null = True, blank = True)
    datetime          = models.DateTimeField(auto_now=True)
    major_version     = models.CharField(max_length=4, null = True, blank = True)
    crashed           = models.NullBooleanField()
    extra_test_args   = models.CharField(max_length=256, null = True, blank = True)
    fatal_message     = models.CharField(max_length=256,  null = True, blank = True)
    exitstatus        = models.CharField(max_length=32, null = True, blank = True)
    returncode        = models.CharField(max_length=3, null = True, blank = True)
    log               = models.CharField(max_length=256, null = True, blank = True)
    state             = models.CharField(max_length=9, db_index = True)

    def __unicode__(self):
        return '%s %s %s' % (self.worker, self.unittestbranch.test, self.extra_test_args)

    class Meta:
        db_table = 'UnitTestRun'

class UnitTestRunForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = UnitTestRun

# http://dev.mysql.com/doc/refman/5.1/en/charset-unicode-utf8.html
# Only supports 3-byte utf-8 in MySQL 5.1.
# http://stackoverflow.com/questions/3220031/how-to-filter-or-replace-unicode-characters-that-would-take-more-than-3-bytes-i
class UnitTestResult(models.Model): #UnitTestResult(AbstractProduct):
    testrun           = models.ForeignKey(UnitTestRun)
    unittest_id       = models.CharField(max_length=512)
    unittest_result   = models.CharField(max_length=512)
    unittest_message  = models.TextField()

    def __unicode__(self):
        return self.unittest_result

    class Meta:
        db_table = 'UnitTestResult'

class UnitTestResultForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = UnitTestResult

class UnitTestCrash(AbstractCrash):
    testrun           = models.ForeignKey(UnitTestRun)
    crash             = models.ForeignKey(Crash)

    class Meta:
        db_table = 'UnitTestCrash'

class UnitTestCrashForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = UnitTestCrash

class UnitTestCrashDumpMetaData(AbstractCrashDumpMetaData):
    crash             = models.ForeignKey(UnitTestCrash)

    class Meta:
        db_table = 'UnitTestCrashDumpMetaData'

class UnitTestCrashDumpMetaDataForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = UnitTestCrashDumpMetaData

class UnitTestAssertion(AbstractAssertion):
    testrun           = models.ForeignKey(UnitTestRun)
    assertion         = models.ForeignKey(Assertion)

    class Meta:
        db_table = 'UnitTestAssertion'

class UnitTestAssertionForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = UnitTestAssertion

class UnitTestValgrind(AbstractValgrind):
    testrun           = models.ForeignKey(UnitTestRun)
    valgrind          = models.ForeignKey(Valgrind)

    class Meta:
        db_table = 'UnitTestValgrind'

class UnitTestValgrindForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = UnitTestValgrind

##############################

class SocorroRecord(models.Model):
    """ Data loaded directly from the nightly crash dump files. """

    signature         = models.CharField(max_length=255, null=True, db_index=True)
    url               = models.CharField(max_length=1000, blank=True, null=True, db_index=True) # could just exclude those records when uploading.
    uuid              = models.CharField(max_length=36)
    client_crash_date = models.DateTimeField(null=True, blank=True)
    date_processed    = models.DateTimeField(null=True, blank=True)
    last_crash        = models.IntegerField(null=True)
    product           = models.CharField(max_length=8, db_index=True)
    version           = models.CharField(max_length=16, db_index=True)
    build             = models.CharField(max_length=16)
    branch            = models.CharField(max_length=16, db_index=True)
    os_name           = models.CharField(max_length=10,   null = True, blank = True, db_index=True)
    os_full_version   = models.CharField(max_length=100,  null = True, blank = True, db_index=True)
    os_version        = models.CharField(max_length=10,    null = True, blank = True, db_index=True)
    cpu_info          = models.CharField(max_length=54,   null = True, blank = True, db_index=True)
    cpu_name          = models.CharField(max_length=16,   null = True, blank = True, db_index=True)
    address           = models.CharField(max_length=18,   null = True, blank = True)
    bug_list          = models.CharField(max_length=3000,  null = True, blank = True)
    user_comments     = models.TextField(null = True, blank = True)
    uptime_seconds    = models.IntegerField(null = True)
    adu_count         = models.IntegerField(null = True)
    topmost_filenames = models.CharField(max_length=256,  null = True, blank = True)
    addons_checked    = models.CharField(max_length=9,    null = True, blank = True)
    flash_version     = models.CharField(max_length=33,   null = True, blank = True)
    hangid            = models.CharField(max_length=36,   null = True, blank = True)
    reason            = models.CharField(max_length=255,  null = True, blank = True)
    process_type      = models.CharField(max_length=8,   null = True, blank = True) # currently \N -> browser, 'plugin'->'plugin'
    app_notes         = models.TextField(null = True, blank = True)
    user_id           = models.IntegerField(null = True)

    def __unicode__(self):
        if self.signature is None:
            return 'None'
        else:
            return self.signature

    class Meta:
        db_table = 'SocorroRecord'

class SocorroRecordForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = SocorroRecord

class SiteTestRun(AbstractProduct):
    worker            = models.ForeignKey(Worker,         null = True, blank = True)
    socorro           = models.ForeignKey(SocorroRecord)
    changeset         = models.CharField(max_length=16,   null = True, blank = True)
    datetime          = models.DateTimeField(auto_now=True)
    major_version     = models.CharField(max_length=4)
    bug_list          = models.CharField(max_length=256,  null = True, blank = True)
    crashed           = models.NullBooleanField()
    extra_test_args   = models.CharField(max_length=256,  null = True, blank = True)
    steps             = models.TextField(null = True, blank = True) # CouchDB: this was an array in the couchdb version. do we need this? It is not currently used.
    fatal_message     = models.CharField(max_length=256,  null = True, blank = True)
    exitstatus        = models.CharField(max_length=32,   null = True, blank = True)
    returncode        = models.CharField(max_length=3, null = True, blank = True)
    log               = models.CharField(max_length=256,  null = True, blank = True)
    priority          = models.CharField(max_length=1, db_index = True)
    state             = models.CharField(max_length=9, db_index = True)

    def __unicode__(self):
        if self.worker:
            return "%s %s" % (self.socorro.signature, self.worker.hostname)
        else:
            return "%s %s" % (self.socorro.signature, None)

    class Meta:
        db_table = 'SiteTestRun'
        index_together = [['priority', 'state', 'os_name', 'os_version',
                           'cpu_name', 'build_cpu_name', 'buildtype']]

class SiteTestRunForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = SiteTestRun

# Should this and UnitTestCrash be ManyToMany relationships?
class SiteTestCrash(AbstractCrash):
    testrun           = models.ForeignKey(SiteTestRun)
    crash             = models.ForeignKey(Crash)

    class Meta:
        db_table = 'SiteTestCrash'

class SiteTestCrashForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = SiteTestCrash

class SiteTestCrashDumpMetaData(AbstractCrashDumpMetaData):
    crash            = models.ForeignKey(SiteTestCrash)

    class Meta:
        db_table = 'SiteTestCrashDumpMetaData'

class SiteTestCrashDumpMetaDataForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = SiteTestCrashDumpMetaData

class SiteTestAssertion(AbstractAssertion):
    testrun           = models.ForeignKey(SiteTestRun)
    assertion         = models.ForeignKey(Assertion)

    class Meta:
        db_table = 'SiteTestAssertion'

class SiteTestAssertionForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = SiteTestAssertion

class SiteTestValgrind(AbstractValgrind):
    testrun           = models.ForeignKey(SiteTestRun)
    valgrind          = models.ForeignKey(Valgrind)

    class Meta:
        db_table = 'SiteTestValgrind'

class SiteTestValgrindForm(ModelForm):
    class Meta:
        fields = "__all__"
        model = SiteTestValgrind

# Singleton tables
