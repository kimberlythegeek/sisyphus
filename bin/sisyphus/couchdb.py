# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla Crash Automation Testing.
#
# The Initial Developer of the Original Code is
# Mozilla Corporation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
# Bob Clary
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import os
import time
import sys
import re
import subprocess
import traceback

# http://mikeal.github.com/couchquery/
import couchquery

# http://code.google.com/p/httplib2/
import httplib2

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json

sisyphus_dir     = os.environ["TEST_DIR"]
sys.path.append(os.path.join(sisyphus_dir, 'bin'))

import sisyphus.utils

class Database():
    def __init__(self, dburi):
        self.dburi   = dburi
        self.db      = couchquery.Database(dburi)
        http = httplib2.Http()
        self.status  = None
        self._design = {}
        self.debug   = False
        self.max_db_attempts  = range(10) # used outside of module

        try:
            self.connectToDatabase(None)
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            message = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

            if not re.search('no_db_file', message):
                raise

            for attempt in self.max_db_attempts:
                try:
                    couchquery.createdb(self.db)
                    break
                except KeyboardInterrupt:
                    raise
                except SystemExit:
                    raise
                except:
                    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                    errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)
                    print('Database: %s, attempt: %d, exception: %s' % (self.db.dburi, attempt, errorMessage))
                    if not re.search('/(couchquery|httplib2)/', errorMessage):
                        raise
                    time.sleep(60)


    def logMessage(self, s, reconnect = True):

        id = os.uname()[1]
        s  = sisyphus.utils.makeUnicodeString(s)

        log_doc = {
            "datetime"  : sisyphus.utils.getTimestamp(hiresolution=True),
            "worker_id" : id,
            "message"   : u"%s: %s" % (id, s),
            "type"      : "log"
            }

        print "%s: %s: %s" % (id, log_doc["datetime"], log_doc["message"])

        # don't use createDocument here as it may cause an infinite loop
        # since logMessage is called from inside the exception handler of
        # createDocument
        for attempt in self.max_db_attempts:
            try:
                docinfo = self.db.create(log_doc)
                log_doc["_id"]  = docinfo["id"]
                log_doc["_rev"] = docinfo["rev"]
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                print('logMessage: attempt: %d, exception: %s' % (attempt, errorMessage))

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                # reconnect to the database in case it has dropped
                if reconnect:
                    self.connectToDatabase(range(1))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("logMessage: aborting after %d attempts" % (self.max_db_attempts[-1]+1))
            time.sleep(60)

    def debugMessage(self, s, reconnect = True):
        if self.debug:
            self.logMessage(s, reconnect)

    def getDocument(self, id, reconnect = True):
        document = None

        for attempt in self.max_db_attempts:
            try:
                document = self.db.get(id)
                break
            except couchquery.CouchDBDocumentDoesNotExist:
                return None
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.logMessage('getDocument: attempt: %d, id: %s, exception: %s' %
                                    (attempt, id, errorMessage))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("getDocument: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))

            time.sleep(60)

        if attempt > 0:
            self.logMessage('getDocument: attempt: %d, success' % (attempt))

        return document

    def createDocument(self, document, reconnect = True):

        for attempt in self.max_db_attempts:
            try:
                docinfo = self.db.create(document)
                document["_id"] = docinfo["id"]
                document["_rev"] = docinfo["rev"]
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if exceptionType == couchquery.CouchDBException and re.search('Document update conflict', str(exceptionValue)):
                    temp_document = self.getDocument(document["_id"])
                    call_stack = traceback.format_stack()
                    self.logMessage('createDocument: attempt: %d, update conflict: call_stack: %s, local: %s, remote: %s, exception: %s' %
                               (attempt, call_stack, document, temp_document, errorMessage))
                    document["_rev"] = temp_document["_rev"]
                    self.updateDocument(document, True)
                    break

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.logMessage('createDocument: attempt: %d, type: %s, exception: %s' % (attempt, document['type'], errorMessage))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("createDocument: aborting after %d attempts" % (self.max_db_attempts[-1]+1))

            time.sleep(60)

        if attempt > 0:
            self.logMessage('createDocument: attempt: %d, success' % (attempt))

    def updateDocument(self, document, reconnect = True, owned = False):
        """
        Update a document handling database connection errors.

        owned = False (the default) means that document update conflicts
        will throw an Exception('updateDocumentConflict') which must be handled
        by the calller.

        owned = True means the current document will overwrite any conflicts
        due to other updates to the document.
        """

        for attempt in self.max_db_attempts:

            try:
                docinfo = self.db.update(document)
                document["_rev"] = docinfo["rev"]
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if exceptionType == couchquery.CouchDBException and re.search('Document update conflict', str(exceptionValue)):
                    if not owned:
                        raise Exception('updateDocumentConflict')

                    self.logMessage('updateDocument: owner will overwrite changes to type: %s, id: %s, rev: %s, exception: %s' %
                                    (document['type'], document['_id'], document['_rev'], errorMessage))
                    temp_document = self.getDocument(document["_id"])
                    document["_rev"] = temp_document["_rev"]
                    docinfo = self.db.update(document)
                    document["_rev"] = docinfo["rev"]
                    break

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.logMessage('updateDocument: attempt: %d, type: %s, exception: %s' % (attempt, document['type'], errorMessage))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("updateDocument: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))
            time.sleep(60)

        if attempt > 0:
            self.logMessage('updateDocument: attempt: %d, success' % (attempt))

    def saveAttachment(self, document, name, data, content_type, reconnect = True, owned = False,):
        """
        Save the string contained in data as an external attachment of the document with name
        and content_type. Return the updated document.
        """

        resp = None
        content = None

        if content_type is None:
            content_type = 'text/plain'

        data = data.encode('utf-8')

        for attempt in self.max_db_attempts:
            try:
                # to keep the revisions current we need to save the current revision of the document
                # first.
                self.updateDocument(document)
                http = httplib2.Http()
                uri  = '%s/%s/%s?rev=%s' % (self.dburi, document['_id'], name, document['_rev'])
                self.debugMessage('saveAttachment: %s' % uri)
                resp, content = http.request(uri, 'PUT', body=data, headers={'content-type':content_type})
                content = json.loads(content)
                # need to retrieve the document to obtain the attachment info
                document = self.getDocument(document['_id'])
                self.debugMessage('saveAttachment: %s, %s' % (resp, content))
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('/(httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.logMessage('saveAttachment: attempt: %d, type: %s, id: %s, rev: %s, exception: %s' %
                                    (attempt, document['type'], document['_id'], document['_rev'], errorMessage))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("saveAttachment: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))

            time.sleep(60)

        if attempt > 0:
            self.logMessage('saveAttachment: attempt: %d, success' % (attempt))

        return document

    def saveFileAttachment(self, document, name, filepath, content_type, reconnect = True, owned = False,):
        """
        Save the file referenced as filepath as an external attachment of the document with name
        and content_type. Return the updated document.
        """

        if content_type is None:
            content_type = 'text/plain'

        for attempt in self.max_db_attempts:
            try:
                # to keep the revisions current we need to save the current revision of the document
                # first.
                self.updateDocument(document)
                http = httplib2.Http()
                uri  = '%s/%s/%s?rev=%s' % (self.dburi, document['_id'], name, document['_rev'])
                self.debugMessage('saveFileAttachment: %s' % uri)

                proc = subprocess.Popen(['curl', '-T', filepath, '-H', 'Content-Type: %s' % content_type, uri],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        close_fds=True)
                stdout = proc.communicate()[0]

                # need to retrieve the document to obtain the attachment info
                document = self.getDocument(document['_id'])
                self.debugMessage('saveFileAttachment: %s, %s' % (uri, stdout))
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('/(httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.logMessage('saveFileAttachment: attempt: %d, type: %s, id: %s, rev: %s, exception: %s' %
                                    (attempt, document['type'], document['_id'], document['_rev'], errorMessage))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("saveFileAttachment: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))

            time.sleep(60)

        if attempt > 0:
            self.logMessage('saveFileAttachment: attempt: %d, success' % (attempt))

        return document

    def deleteDocument(self, document, reconnect = True, owned = False):
        """
        Delete a document handling database connection errors.

        owned = False (the default) means that document update conflicts
        will throw an Exception('deleteDocumentConflict') which must be handled
        by the calller.

        owned = True means the current document will delete the document regardless of
        any conflicts due to other updates to the document.
        """

        for attempt in self.max_db_attempts:
            try:
                docinfo = self.db.delete(document)
                document["_rev"] = docinfo["rev"]
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if exceptionType == couchquery.CouchDBException:
                    if re.search('Delete failed {"error":"not_found","reason":"deleted"}', str(exceptionValue)):
                        self.logMessage('deleteDocument: ignore already deleted document. type: %s, id: %s' % (document["type"], document["_id"]))
                        break
                    if not owned:
                        raise Exception('deleteDocumentConflict')
                    if re.search('Document update conflict', str(exceptionValue)):
                        self.logMessage('deleteDocument: owner will attempt to deleted updated document')
                        temp_document = self.getDocument(document["_id"])
                        document["_rev"] = temp_document["_rev"]
                        docinfo = self.db.delete(document)
                        document["_rev"] = docinfo["rev"]
                        break

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.logMessage('deleteDocument: attempt: %d, type: %s, id: %s, rev: %s, exception: %s' %
                                    (attempt, document['type'], document['_id'], document['_rev'], errorMessage))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("deleteDocument: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))

            time.sleep(60)

        if attempt > 0:
            self.logMessage('deleteDocument: attempt: %d, success' % (attempt))

    def createLock(self, document, reconnect = True, attempts = None):
        """
        createLock will attempt to create a lock document of the format:
        {'type' : 'lock', 'owner' : 'ownerid', '_id' : 'lockname' }

        createLock will return True upon successful completion of the lock
        and False if the lock was not able to be created.

        createLock will raise Exception('InvalidLockDocument') if called with a non lock
        document.

        createLock will pass through any exceptions not related to CouchDB update conflicts.
        """

        if document['type'] != 'lock':
            raise Exception('InvalidLockDocument')

        if attempts is None:
            attempts = self.max_db_attempts

        for attempt in attempts:
            try:
                docinfo = self.db.create(document)
                document["_id"] = docinfo["id"]
                document["_rev"] = docinfo["rev"]
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if exceptionType == couchquery.CouchDBException and re.search('Document update conflict', str(exceptionValue)):
                    # treat couchdb update exceptions as temporary recoverable
                    # errors.
                    pass

                elif not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.debugMessage('createLock: attempt: %d, type: %s, exception: %s' % (attempt, document['type'], errorMessage))

            if attempt == attempts[-1]:
                self.logMessage("createLock: aborting after %d attempts" % (attempts[-1]+1))
                return False

            time.sleep(1)

        if attempt > 0:
            self.debugMessage('createLock: attempt: %d, success' % (attempt))

        return True

    def deleteLock(self, document, reconnect = True, owned = False):
        """
        Delete an existing lock document.

        deleteLock will raise Exception('InvalidLockDocument') if called with a non lock
        document.

        deleteLock will raise Exception("deleteDocument: aborting after %d attempts"
                                        % (self.max_db_attempts[-1] + 1))
        if it fails to delete the lock after the maximum number of attempts.
        This may result in broken lock which must be resolved by user intervention.

        deleteLock will pass through any exceptions not related to CouchDB.
        This may result in broken lock which must be resolved by user intervention.
        """

        if document['type'] != 'lock':
            raise Exception('InvalidLockDocument')

        for attempt in self.max_db_attempts:
            try:
                lock_document = self.getDocument(document['_id'])
                if not lock_document:
                    self.logMessage('deleteLock: ignoring attempt to delete missing lock %s' % document)
                    break
                if lock_document['owner'] != document['owner']:
                    self.logMessage('deleteLock: ignoring attempt to delete unowned lock %s' % lock_document)
                    break

                docinfo = self.db.delete(document)
                document["_rev"] = docinfo["rev"]
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if exceptionType == couchquery.CouchDBException:
                    if re.search('Delete failed {"error":"not_found","reason":"deleted"}', str(exceptionValue)):
                        self.logMessage('deleteLock: ignoring already deleted lock: %s' % document)
                        break
                    if re.search('Document update conflict', str(exceptionValue)):
                        lock_document = self.getDocument(document["_id"])
                        if lock_document['owner'] != document['owner']:
                            self.logMessage('deleteLock: ignoring attempt to delete unowned conflicted lock %s' % lock_document)
                            break
                        self.logMessage('deleteLock: attempt to delete owned conflicted lock %s' % lock_document)
                        document["_rev"] = lock_document["_rev"]
                        docinfo = self.db.delete(document)
                        document["_rev"] = docinfo["rev"]
                        break

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                if reconnect:
                    self.connectToDatabase(range(1))
                    self.logMessage('deleteLock: attempt: %d, type: %s, id: %s, rev: %s, exception: %s' %
                                    (attempt, document['type'], document['_id'], document['_rev'], errorMessage))

            if attempt == self.max_db_attempts[-1]:
                raise Exception("deleteLock: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))

            time.sleep(5)

        if attempt > 0:
            self.logMessage('deleteLock: attempt: %d, success' % (attempt))

    def connectToDatabase(self, attempts = None):
        """
        Attempt to access the database and keep trying for attempts.
        If attempts not specified, then use max_db_attempts.
        """
        messagequeue = []
        if attempts is None:
            attempts = self.max_db_attempts

        for attempt in attempts:
            try:
                http = httplib2.Http()
                resp, content = http.request(self.dburi, method = 'GET')
                if resp['status'] == '404':
                    raise Exception('no_db_file')
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = ('connectToDatabase: %s: %s, database %s not available, exception: %s' %
                                (os.uname()[1], sisyphus.utils.getTimestamp(), self.dburi,
                                 sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)))

                if re.search('no_db_file', errorMessage):
                    raise

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                # recreate the database object.
                self.db      = couchquery.Database(self.dburi)

                messagequeue.append(errorMessage)
                print(errorMessage)

            time.sleep(60)

        if attempt > 0:
            for message in messagequeue:
                self.logMessage(message)

            self.logMessage('connectToDatabase: attempt: %d, success connecting to %s' % (attempt, self.dburi))

    def checkDatabase(self):
        try:

            # compact database if its size has doubled.
            http = httplib2.Http()
            resp, content = http.request(self.dburi, method = 'GET')

            if resp['status'].find('2') != 0:
                self.logMessage('checkDatabase: GET %s bad response: %s, %s' % (self.dburi, resp, content))
            else:
                new_status = json.loads(content)

                if not self.status:
                    self.status = new_status
                elif new_status['compact_running']:
                    pass
                elif new_status['disk_size'] < self.status['disk_size']:
                    self.status = new_status
                elif new_status['disk_size'] > 2 * self.status['disk_size']:
                    self.logMessage('checkDatabase: compacting %s' % self.dburi)
                    self.status = new_status

                    resp, content = http.request(self.dburi + '/_compact', method='POST', headers={"Content-Type":"application/json"})
                    if resp['status'].find('2') != 0:
                        self.logMessage('checkDatabase: POST %s/_compact response: %s, %s' % (self.dburi, resp, content))
                    else:
                        time.sleep(5)
                        resp, content = http.request(self.dburi + '/_view_cleanup', method='POST', headers={"Content-Type":"application/json"})
                        if resp['status'].find('2') != 0:
                            self.logMessage('checkDatabase: POST %s/_compact/_view_cleanup response: %s, %s' % (self.dburi, resp, content))
                        else:
                            time.sleep(5)

            # compact design documents if their sizes have doubled.
            design_docs = self.getRows(self.db.views.all, '_design/', '_design/' + 100*'z', include_docs=True)

            for design_doc in design_docs:
                design_doc_name = design_doc['_id'][len('_design/'):]


                resp, content = http.request('%s/_design/%s/_info' % (self.dburi, design_doc_name), method='GET')
                if resp['status'].find('2') != 0:
                    self.logMessage('checkDatabase: GET %s/_design/%s/_info response: %s, %s' % (self.dburi, design_doc_name, resp, content))
                else:
                    new_status = json.loads(content)

                    if design_doc_name not in self._design:
                        self._design[design_doc_name] = new_status
                    elif new_status['view_index']['compact_running'] or new_status['view_index']['updater_running']:
                        pass
                    elif new_status['view_index']['disk_size'] < self._design[design_doc_name]['view_index']['disk_size']:
                        self._design[design_doc_name] = new_status
                    elif new_status['view_index']['disk_size'] > 2 * self._design[design_doc_name]['view_index']['disk_size']:
                        self.logMessage('checkDatabase: compacting %s/_design/%s' % (self.dburi, design_doc_name))
                        self._design[design_doc_name] = new_status

                        resp, content = http.request('%s/_compact/%s' % (self.dburi, design_doc_name), method='POST', headers={"Content-Type":"application/json"})
                        if resp['status'].find('2') != 0:
                            self.logMessage('checkDatabase: POST %s/_compact/%s response: %s, %s' % (self.dburi, design_doc_name, resp, content))
                    else:
                        # Retrieve one document from a view in the design document
                        # to force an update in order to improve ui responsiveness.
                        resp, content = http.request('%s/_design/%s' % (self.dburi, design_doc_name))
                        if resp['status'].find('2') != 0:
                            pass # skip on error
                        else:
                            jcontent = json.loads(content)
                            if 'views' in jcontent:
                                for view_name in jcontent['views']:
                                    http.request('%s/_design/%s/_view/%s?limit=1' % (self.dburi, design_doc_name, view_name))
                                    break

        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

            if not re.search('/httplib2/', errorMessage):
                raise

            self.connectToDatabase(range(1))
            self.logMessage('checkDatabase: exception %s: %s' % (str(exceptionValue), sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)))

    def getDatabase(self):
        return self.db

    def sync_design_doc(self, design_dir):
        import glob

        design_doc_dirs = glob.glob(os.path.join(design_dir, '*'))

        for design_doc_dir in design_doc_dirs:
            if os.path.isdir(design_doc_dir):
                self.db.sync_design_doc(os.path.basename(design_doc_dir), design_doc_dir)

    def getRows(self, view, startkey = None, endkey = None, include_docs = None):
        """
        return rows from view matching startkey, endkey with
        connection recovery.
        """
        if include_docs is None:
            include_docs = False

        rows = None

        for attempt in self.max_db_attempts:
            try:
                if startkey and endkey:
                    rows = view(startkey=startkey, endkey=endkey, include_docs=include_docs)
                elif startkey:
                    rows = view(startkey=startkey, include_docs=include_docs)
                else:
                    rows = view(include_docs=include_docs)

                if include_docs:
                    # the view does not define the value as the full document.
                    # retrieve the document from the raw_rows.
                    rows = [row['doc'] for row in rows.raw_rows()]
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
                errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

                if not re.search('/(couchquery|httplib2)/', errorMessage):
                    raise

                # reconnect to the database in case it has dropped
                self.connectToDatabase(None)

            if attempt == self.max_db_attempts[-1]:
                raise Exception("getRows: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))
            time.sleep(60)

        return rows

