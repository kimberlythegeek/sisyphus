function(doc) {
  try
  {
    switch(doc.type)
    {
    case 'result_header_crashtest':
      emit([doc.url, doc.datetime, doc._id, '1'], null);
      break;

    case 'result_crash':
      emit([doc.location_id, doc.datetime, doc.result_id, '2', doc.crash, doc.crashsignature], null);
      break;

    case 'result_assertion':
      emit([doc.location_id, doc.datetime, doc.result_id, '3', doc.assertion, doc.assertionfile], null);
      break;

    case 'result_valgrind':
      emit([doc.location_id, doc.datetime, doc.result_id, '4', doc.valgrind, doc.valgrindsignature], null);
      break;
    }
  }
  catch(ex)
  {
  }
}