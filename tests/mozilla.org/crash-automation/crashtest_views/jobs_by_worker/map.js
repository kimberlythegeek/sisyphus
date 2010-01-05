function (doc) {
  if (doc.type == 'signature' && doc.worker) {
    emit(doc.worker, doc)
  }
}