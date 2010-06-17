function(doc) {
  var i;
  switch(doc.type)
  {

  case 'assertion':
    if ('location_id_list' in doc) {
      for (i = 0; i < doc.location_id_list.length; i++)
        emit([doc.location_id_list[i], doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    }
    break;

  case 'crash':
    if ('location_id_list' in doc) {
      for (i = 0; i < doc.location_id_list.length; i++)
        emit([doc.location_id_list[i], doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    }
    break;

  case 'valgrind':
    if ('location_id_list' in doc) {
      for (i = 0; i < doc.location_id_list.length; i++)
        emit([doc.location_id_list[i], doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], null);
    }
    break;

  }


}