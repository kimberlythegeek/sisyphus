function (doc) {
  try
  {
    if (doc.type == "tests") {
      emit(doc._id, doc);
    }
  }
  catch(ex)
  {
  }
}
