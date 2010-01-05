function(doc) {
  if (doc.type == 'result' && doc.reproduced)
     emit([doc.triage, doc.url, doc._id, doc.datetime], doc);
}