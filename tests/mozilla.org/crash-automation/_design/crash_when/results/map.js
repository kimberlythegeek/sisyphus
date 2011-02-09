function (doc) {
  try
  {
    switch (doc.type) {
    case 'result_header_crashtest':
    case 'result_header_unittest':
      emit([doc.datetime, doc.type], null);
      break;
    case 'result_assertion':
      emit([doc.datetime, doc.type, doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
      break;
    case 'result_crash':
      emit([doc.datetime, doc.type, doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
      break;
    case 'result_valgrind':
      emit([doc.datetime, doc.type, doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
      break;
    }
  }
  catch(ex)
  {
  }
}
