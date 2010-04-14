function (doc) {
  if (doc.type == 'log')
    emit(doc.datetime, null)
}
