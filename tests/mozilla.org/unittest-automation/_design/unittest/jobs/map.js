function (doc) {
  if (doc.type == 'job_unittest') {
    emit([doc.os_name, doc.cpu_name, doc.os_version, doc.branch], doc);
  }
}
