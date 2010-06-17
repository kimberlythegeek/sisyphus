function(doc) {
  var i;
  switch(doc.type)
  {
  case 'result':
    emit([doc.url, doc._id, doc.type, doc.signature], null);
    break;

  case 'result_assertion':
    emit([doc.location_id, doc.result_id, doc.type, doc.assertion, doc.assertionfile], null);
    break;

  case 'result_crash':
    emit([doc.location_id, doc.result_id, doc.type, doc.crash, doc.crashsignature], null);
    break;

  case 'result_valgrind':
    emit([doc.location_id, doc.result_id, doc.type, doc.valgrind, doc.valgrindsignature], null);
    break;
  }
}