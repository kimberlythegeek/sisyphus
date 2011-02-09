function (doc) {
  try
  {
    if (doc.type == 'signature' && doc.worker) {
      emit(doc.worker, doc)
    }
  }
  catch(ex)
  {
  }
}
