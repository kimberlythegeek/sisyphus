function (doc) {
  if (doc.type == 'signature')
    emit([doc.date, doc.os_name, doc.os_version], 1);
}
