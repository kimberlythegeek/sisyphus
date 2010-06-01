function (doc) {
  if (doc.type == 'branches')
    emit(null, doc);
}