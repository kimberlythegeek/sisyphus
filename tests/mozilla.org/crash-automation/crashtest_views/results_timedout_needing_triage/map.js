function(doc) {
  if (doc.type == 'result' && doc.exitstatus == 'TIMED OUT' && !doc.triage)
     emit([doc.datetime, doc.url, doc._id], doc);
}