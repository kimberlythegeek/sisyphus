
function (doc) {
  if (doc.type == 'valgrind') {
    emit([doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], doc);
  }
}
