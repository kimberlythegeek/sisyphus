
function (doc) {
  if (doc.type == 'crash') {
    emit([doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
  }
}
