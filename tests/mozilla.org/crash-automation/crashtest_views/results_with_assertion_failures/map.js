function(doc) {
  if (doc.type == 'result' && doc.assertionfail)
     emit([doc.datetime, doc.url, doc._id], doc);
}