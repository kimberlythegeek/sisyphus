function(doc) {
  try
  {
    if (doc._conflicts) {
      emit(null, [doc._rev].concat(doc._conflicts));
    }
  }
  catch(ex)
  {
  }
}
