
function (doc) {
  if (doc.type == 'result_assertion') {
    emit([doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
  }
}
