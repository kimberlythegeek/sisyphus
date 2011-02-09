function (doc) {
  try
  {
    if (doc.type == 'branches')
      emit(null, doc);
  }
  catch(ex)
  {
  }
}