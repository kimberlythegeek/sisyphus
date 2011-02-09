function (doc) {
  switch(doc.type) {
  case 'result_header_crashtest':
  case 'result_header_unittest':
    emit([doc._id, doc.type], null);
    break;
  case 'result_crash':
    emit([doc.result_id, doc.type, doc.crash, doc.crashsignature], null);
    break;
  case 'result_valgrind':
    emit([doc.result_id, doc.type, doc.valgrind, doc.valgrindsignature], null);
    break;
  case 'result_assertion':
    emit([doc.result_id, doc.type, doc.assertion, doc.assertionfile], null);
    break;
  case 'result_unittest':
    emit([doc.result_id, doc.type, doc.unittest_id], null);
    break;
  }
}
