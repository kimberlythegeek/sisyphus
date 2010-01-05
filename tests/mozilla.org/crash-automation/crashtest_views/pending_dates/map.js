function(doc) {
  if (doc.type == 'signature')
    emit(doc.date, 1);
}
