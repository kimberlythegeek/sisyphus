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
        self.http    = httplib2.Http()
        self.status  = None
        self.debug   = False
        self.max_db_attempts  = range(10) # used outside of module

        try:
            self.connectToDatabase()
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            message = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

            if re.search('no_db_file', message):
                couchquery.createdb(self.db)
            else:
                raise

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

                # reconnect to the database in case it has dropped
                if reconnect and re.search('conn_request', errorMessage):
                    self.connectToDatabase()
                else:
                    raise

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

                # reconnect to the database in case it has dropped
                if reconnect and re.search('conn_request', errorMessage):
                    self.connectToDatabase()
                    self.logMessage('getDocument: attempt: %d, id: %s, exception: %s' %
                               (attempt, id, errorMessage))
                else:
                    raise

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
                    document["_rev"] = temp_document["_rev"]
                    self.logMessage('createDocument: attempt: %d, update type: %s, _id: %s, _rev: %s' %
                               (attempt, document['type'], document["_id"], document["_rev"]))
                    self.updateDocument(document, True)
                    break
                elif reconnect and re.search('conn_request', errorMessage):
                    # reconnect to the database in case it has dropped
                    self.connectToDatabase()
                    self.logMessage('createDocument: attempt: %d, type: %s, exception: %s' % (attempt, document['type'], errorMessage))
                else:
                    raise

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
                elif reconnect and re.search('conn_request', errorMessage):
                    # reconnect to the database in case it has dropped
                    self.connectToDatabase()
                    self.logMessage('updateDocument: attempt: %d, type: %s, exception: %s' % (attempt, document['type'], errorMessage))
                else:
                    raise
            if attempt == self.max_db_attempts[-1]:
                raise Exception("updateDocument: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))
            time.sleep(60)

        if attempt > 0:
            self.logMessage('updateDocument: attempt: %d, success' % (attempt))

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
                elif reconnect and re.search('conn_request', errorMessage):
                    # reconnect to the database in case it has dropped
                    self.connectToDatabase()
                    self.logMessage('deleteDocument: attempt: %d, type: %s, id: %s, rev: %s, exception: %s' %
                                    (attempt, document['type'], document['_id'], document['_rev'], errorMessage))
                else:
                    raise

            if attempt == self.max_db_attempts[-1]:
                raise Exception("deleteDocument: aborting after %d attempts" % (self.max_db_attempts[-1] + 1))

            time.sleep(60)

        if attempt > 0:
            self.logMessage('deleteDocument: attempt: %d, success' % (attempt))

    def connectToDatabase(self):
        """
        Attempt to access the database and keep trying until you succeed.
        """
        messagequeue = []
        attempt = 0
        while True:
            try:
                resp, content = self.http.request(self.dburi, method = 'GET')
                if resp['status'] == '404':
                    raise Exception('no_db_file')
                break
            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except:
                exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

                message = ('connectToDatabase: %s: %s, database %s not available, exception: %s' %
                           (os.uname()[1], sisyphus.utils.getTimestamp(), self.dburi,
                            sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)))

                if re.search('no_db_file', message):
                    raise

                messagequeue.append(message)
                print(message)

            time.sleep(60)
            attempt += 1

        if attempt > 0:
            for message in messagequeue:
                self.logMessage(message)
                time.sleep(1) # delay each message by a second to keep the log in order
            self.logMessage('connectToDatabase: attempt: %d, success connecting to %s' % (attempt, self.dburi))

    def checkDatabase(self):
        try:

            resp, content = self.http.request(self.dburi, method = 'GET')

            if resp['status'].find('2') != 0:
                self.logMessage('checkDatabase: GET %s bad response: %s, %s' % (self.dburi, resp, content))
            else:
                new_status = json.loads(content)

                if not self.status:
                    self.status = new_status
                elif new_status['compact_running']:
                    # the database is being compacted. wait 1 minute to help
                    # prevent the compaction from never completing due to updates.
                    time.sleep(60)
                    pass
                elif new_status['disk_size'] < self.status['disk_size']:
                    self.status = new_status
                elif new_status['disk_size'] > 2 * self.status['disk_size']:
                    self.logMessage('checkDatabase: compacting %s' % self.dburi)
                    self.status = new_status
                    time.sleep(5)
                    resp, content = self.http.request(self.dburi + '/_compact', method='POST')
                    if resp['status'].find('2') != 0:
                        self.logMessage('checkDatabase: POST %s/_compact response: %s, %s' % (self.dburi, resp, content))
                    else:
                        time.sleep(5)
                        resp, content = self.http.request(self.dburi + '/_view_cleanup', method='POST')
                        if resp['status'].find('2') != 0:
                            self.logMessage('checkDatabase: POST %s/_compact/_view_cleanup response: %s, %s' % (self.dburi, resp, content))
                        else:
                            time.sleep(5)
                            # TODO: figure out a way to enumerate the design docs to compact
                            # them automatically. Until then, everyone uses the same design id 'default'.
                            resp, content = self.http.request(self.dburi + '/_compact/default', method='POST')
                            if resp['status'].find('2') != 0:
                                self.logMessage('checkDatabase: POST %s/_compact/default response: %s, %s' % (self.dburi, resp, content))
        except KeyboardInterrupt:
            raise
        except SystemExit:
            raise
        except:
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()

            errorMessage = sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)

            # reconnect to the database in case it has dropped
            if re.search('conn_request', errorMessage):
                self.connectToDatabase()
                self.logMessage('checkDatabase: exception %s: %s' % (str(exceptionValue), sisyphus.utils.formatException(exceptionType, exceptionValue, exceptionTraceback)))
            else:
                raise

    def getDatabase(self):
        return self.db
