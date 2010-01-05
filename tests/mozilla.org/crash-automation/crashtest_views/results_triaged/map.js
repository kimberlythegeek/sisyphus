function (doc) {
  if (doc.type == 'result' && doc.triage) {
    emit([doc.url, doc._id, doc.datetime], doc);
  }
}