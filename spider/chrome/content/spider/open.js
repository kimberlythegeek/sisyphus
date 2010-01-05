function openSpider(event, queryString)
{
  if (!queryString)
  {
    queryString = '';
  }

  var spiderurl = 'spider.xul' + queryString;

  if (window.location.href.indexOf('chrome:') != -1)
  {
    open('chrome://spider/content/' + spiderurl,
         'spiderwindow', 
         'chrome,dialog=no,resizable');
  }
  else
  {
    window.location.href = spiderurl;
  }
}
