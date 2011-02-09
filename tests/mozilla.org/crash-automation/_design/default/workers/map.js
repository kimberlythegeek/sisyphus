function (doc) {
  try
  {
    if (doc.type.substring(0,7) == 'worker_')
      emit([doc.type, doc._id], doc);
  }
  catch(ex)
  {
  }
}