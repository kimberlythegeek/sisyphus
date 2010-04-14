/* it is interesting if there are no bugs on file or no open bugs on file */
function (doc) {
  if (doc.type == 'result_valgrind' && !doc.suppress && (!doc.bug_list || doc.bug_list.open.length == 0)) {
    emit([doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
  }
}
