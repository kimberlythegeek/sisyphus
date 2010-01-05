function(doc) {
  if (doc.type == 'result' && doc.reproduced)
     emit([doc.url, doc._id, doc.datetime], doc);
}