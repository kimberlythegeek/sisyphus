
function (doc) {
  if (doc.type == 'result_valgrind') {
    emit([doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
  }
}
