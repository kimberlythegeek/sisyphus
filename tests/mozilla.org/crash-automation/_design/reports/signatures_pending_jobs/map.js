function(doc) {
  if (doc.type == 'signature' && !doc.worker)
    emit([doc.signature, doc.major_version, doc.os_name, doc.os_version, doc.cpu_name], null);
}
