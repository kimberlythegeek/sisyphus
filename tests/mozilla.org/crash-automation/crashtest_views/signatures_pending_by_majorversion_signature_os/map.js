function(doc) {
  if (doc.type == 'signature' && !doc.worker)
    emit([doc.major_version, doc.signature, doc.os_name, doc.os_version, doc.cpu_name], doc);
}