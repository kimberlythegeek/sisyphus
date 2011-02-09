function (doc) {
  try
  {
    if (doc.type == 'log')
      emit(doc.datetime, null);
  }
  catch(ex)
  {
  }
}
