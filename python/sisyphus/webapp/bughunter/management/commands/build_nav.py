import os
import pprint

try:
   import simplejson as json
except ImportError:
   import json

from django.conf import settings
from django.template import Template, Context
from django.core.management.base import BaseCommand, CommandError

from datasource.bases.BaseHub import BaseHub
from bughunter.filters.templatetags.bh_unorderedlist import bh_unorderedlist

class Command(BaseCommand):

   args = 'None'
   help = 'Builds the bughunter navigation menu and lookup json'

   nav_lookup_hash = {}
   nav_ui = []

   @staticmethod
   def build_nav(json_nav, children=0, target=[]):
      """
      Recursive function that translates views.json into two datastructures
      that are required by the user interface:

       nav_lookup_hash - An associative array used to lookup items
                         in the unordered HTML list that makes up the
                         navigation menu.

                         key:name, value:view associative array

       nav_ui - A list of lists that will work directly with the django unordered_list
                filter to build the navigation HTML.
      """
      if type(json_nav) == list:
         ##Examine all elements of any list##
         for i in json_nav:
            Command.build_nav(i, children, target)

      elif type(json_nav) == dict:

         if 'read_name' in json_nav:
            ##Child Element##
            Command.nav_lookup_hash[ json_nav['name'] ] = json_nav
            target.append( { 'read_name':json_nav['read_name'], 'name':json_nav['name'] } )
         else:
            for key in json_nav:
               count          = len(target) 
               lastTarget     = target #last list appended to
               target         = list()

               if children != count:
                  ##Nested Parent##
                  lastTarget.append(key)
                  lastTarget.append(target)
               else:
                  ##Parent##
                  Command.nav_ui.append(key)
                  Command.nav_ui.append(target)

               if type(json_nav[key]) == list:
                  children = len( json_nav[key] )
                  Command.build_nav(json_nav[key], children, target)

   def handle(self, *args, **options):

      ##Load data views##
      views_file_obj = open("%s%s" % (settings.ROOT, "/templates/data/views.json"))
      try:
         data_view_file = views_file_obj.read()
      finally:
         views_file_obj.close()
      ##Strip out comments and newlines##
      t = BaseHub.stripPythonComments(data_view_file)
      data_views = BaseHub.deserializeJson(data_view_file)

      Command.build_nav(data_views)

      #Uncomment to see datastructure for debugging
      #pp = pprint.PrettyPrinter(indent=3)
      #self.stdout.write( pp.pformat(Command.nav_ui) ) 

      menu_file_obj = open("%s%s" % (settings.ROOT, "/html/nav/nav_menu.html"), 'w+')
      try:
         menu_file_obj.write( '<ul class="bh-viewtext">\n%s\n</ul>' % (bh_unorderedlist(Command.nav_ui)) )
      finally:
         menu_file_obj.close()

      ##Write out json for the nav_lookup_hash##
      jstring = json.dumps( Command.nav_lookup_hash, ensure_ascii=False )

      html = """<input id="bh_nav_json" type="hidden" value="{{ json_data }}" />"""
      t = Template(html)
      c = Context({ 'json_data':jstring })
      templateString = t.render(c)

      nav_lookup_file_obj = open("%s%s" % (settings.ROOT, "/templates/bughunter.navlookup.html"), 'w+')
      try:
         nav_lookup_file_obj.write(templateString) 
      finally:
         nav_lookup_file_obj.close()
