function(doc) {
  var i;
  switch(doc.type)
  {
  case 'signature':
    var len = doc.urls.length;
    for (i = 0; i < len; i++)
      emit([doc.urls[i], doc.type, doc.signature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  case 'result':
    emit([doc.url, doc.type, doc.signature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  case 'result_assertion':
    emit([doc.location_id, doc.type, doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  case 'result_valgrind':
    emit([doc.location_id, doc.type, doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  case 'result_crash':
    emit([doc.location_id, doc.type, doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;
  }
}