function(doc) {
  if (doc.type == 'result') {
    emit([doc.worker_id, doc.datetime.substring(0,10)], null);
  }
}
