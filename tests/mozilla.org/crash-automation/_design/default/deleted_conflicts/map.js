function(doc) {
  try
  {
    if (doc._deleted_conflicts) {
      emit(null, [doc._rev].concat(doc._deleted_conflicts));
    }
  }
  catch(ex)
  {
  }
}
