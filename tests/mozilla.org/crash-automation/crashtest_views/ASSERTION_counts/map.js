function(doc) {
  if (doc.type == 'result')
    for (assertion in doc.ASSERTIONS)
      emit([assertion, doc.major_version], 1);
}