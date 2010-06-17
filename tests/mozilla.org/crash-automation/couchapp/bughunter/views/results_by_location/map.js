function(doc) {
  switch(doc.type)
  {
  case 'result_header_crashtest':
    emit([doc.url, doc.datetime, doc._id, doc.type], null);
    break;

  case 'result_crash':
    emit([doc.location_id, doc.datetime, doc.result_id, doc.type, doc.crash, doc.crashsignature], null);
    break;

  case 'result_assertion':
    emit([doc.location_id, doc.datetime, doc.result_id, doc.type, doc.assertion, doc.assertionfile], null);
    break;

  case 'result_valgrind':
    emit([doc.location_id, doc.datetime, doc.result_id, doc.type, doc.valgrind, doc.valgrindsignature], null);
    break;
  }
}