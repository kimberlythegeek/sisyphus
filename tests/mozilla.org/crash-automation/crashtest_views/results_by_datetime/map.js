function (doc) {
  if (doc.type == 'result') {
    emit(doc.datetime, doc)
  }
}