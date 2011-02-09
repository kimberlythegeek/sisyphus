function (doc) {
  try
  {
    switch (doc.type) {
    case 'result_header_crashtest':
    case 'result_header_unittest':
      emit([doc.type, doc._id], null);
      break;
    case 'history_assertion':
      emit([doc.type, doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name, doc.firstdatetime], null);
      break;
    case 'result_assertion':
      emit([doc.type, doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name, doc.datetime], null);
      break;
    case 'history_crash':
      emit([doc.type, doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name, doc.firstdatetime], null);
      break;
    case 'result_crash':
      emit([doc.type, doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name, doc.datetime], null);
      break;
    case 'history_valgrind':
      emit([doc.type, doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name, doc.firstdatetime], null);
      break;
    case 'result_valgrind':
      emit([doc.type, doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name, doc.datetime], null);
      break;
    }
  }
  catch(ex)
  {
  }
}