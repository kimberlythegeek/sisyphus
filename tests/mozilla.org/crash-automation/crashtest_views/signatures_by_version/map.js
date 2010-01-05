function(doc) {
  if (doc.type == 'signature' && 'versionhash' in doc)
    for (version in doc.versionhash)
      emit([version, doc.os_name, doc.os_version, doc.cpu_name], doc);
}