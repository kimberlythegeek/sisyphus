function(doc) {
  if (doc.type == 'signature') {
    emit([doc.os_name, doc.os_version, doc.major_version], null);
    emit([doc.os_name, doc.cpu_name, doc.os_version, doc.major_version], null);
    emit([doc.major_version], null);
  }
}