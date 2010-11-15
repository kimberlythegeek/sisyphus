function(head, req) {
  // bangjson templates.index
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js


  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // their priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

             function dumpObject(object) {
               if (!object || typeof object != 'object')
                 return object;
               s = '<ul>';
               for (var prop in object) {
                 s += '<li>' + prop + '=' + dumpObject(object[prop]) + '</li>';
               }
               s += '</ul>';
               return s;
             }

             send('<h2>head properties</h2>')
             send(dumpObject(head));

             send('<h2>request properties</h2>')
             send(dumpObject(req));

             send('<h2>row properties</h2>')
             // loop over view rows, rendering one at a time
             var row, key;
             while (row = getRow()) {
               send(dumpObject(row));
             }
             send('</body>');
             send('</html>');
           });
};
