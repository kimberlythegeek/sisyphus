function (doc) {
  try
  {
    if (doc.type == 'build')
      emit([doc.product, doc.branch, doc.buildtype, doc.os_name, doc.cpu_name], doc);
  }
  catch(ex)
  {
  }
}
