function (doc) {
  if (doc.type == 'worker') {
    emit(doc._id, doc)
  }
}
