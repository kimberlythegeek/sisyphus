/* it is interesting if there are no bugs on file or no open bugs on file */
function (doc) {
  if (doc.type == 'result_crash' && (!doc.bug_list || doc.bug_list.open.length == 0)) {
    emit([doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], doc);
  }
}
