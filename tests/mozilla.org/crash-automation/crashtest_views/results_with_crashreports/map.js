function(doc) {
  if (doc.type == 'result' && doc._attachments.crashreport.length > 0)
     emit([doc.url, doc._id, doc.datetime], doc);
}