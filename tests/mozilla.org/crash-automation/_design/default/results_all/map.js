function(doc) {
  if (doc.type == 'result')
     emit(doc._id, null);
}
