
function (doc) {
  switch (doc.type) {
  case 'result_assertion':
    emit([doc.type, doc.assertion, doc.asssertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  case 'result_crash':
    emit([doc.type, doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  case 'result_valgrind':
    emit([doc.type, doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  }
}
