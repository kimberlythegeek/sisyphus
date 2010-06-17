function (doc) {

  switch(doc.type) {

  case 'assertion':
    emit([doc.type, doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;

  case 'crash':
    emit([doc.type, doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;

  case 'valgrind':
    emit([doc.type, doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    break;

  }

}
