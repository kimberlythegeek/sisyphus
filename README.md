
# Tantalus (Bughunter 2.0)

## Requirements

To run a local development environment, you must have [Docker](https://www.docker.com/get-started) installed and its daemon running.

Currently, to access Tantalus, you need an LDAP account, as well as access to the bughunter LDAP group. (Soon to be changed to the tantalus LDAP group)

You also need to be connected to [Mozilla's VPN](https://mana.mozilla.org/wiki/display/SD/VPN).

## Usage

To run the web app and database containers, type the following command into your terminal:

```bash
docker-compose build && docker-compose up
```

To restart the containers, simply add the `docker-compose down` command:

```bash
docker-compose down && docker-compose build && docker-compose up
```

The web app will be accessible at [http://localhost:8000/bughunter](http://localhost:8000/bughunter)

The workers are viewable at [http://localhost:8000/#admin/workers](http://localhost:8000/#admin/workers)

## Files

All web related files are contained in this directory python/sisyphus/webapp

The following file inventory is a list of the critical bughunter files, there
are other things floating around but this is the crux of it all...

      Web Application
         bughunter/views.py                          - Django apps for admin and data views
         bughunter/models.py                         - Django models for the admin application
         bughunter/urls.py                           - Django url routing for admin and data views

         bughunter/filters/bh_unorderedlist.py       - Specialized template tag for writing out <ul></ul>
                                                       for the data view navigation menu.
         bughunter/management/commands/build_nav.py  - Command for manage.py that will generate bughunter.navlookup.html
                                                       and nav_menu.html

      Service
         service/bin/bughunter                       - Bash script to start the fcgi service with manage.py

      SQL
         procs/bughunter.json                        - SQL statements used with

      View Definitions
         templates/data/views.json                   - A json structure that describes all data views and their
                                                       hierarchical organization in the navigation menu.

      View HTML
         templates/bughunter.views.html              - Main bughunter view page
         templates/bughunter.navlookup.html          - Template include holding the views.json lookup struct
         templates/help/bughunter.generic.help.html  - Help main page
         templates/help/nav/nav_menu.html            - Navigation menu for data views gerated by "manage.py build_nav"
                                                       command

         templates/help/...                          - Various help includes

         html/control_panel/...                      - Various control panels that are attached
                                                       to related data views.
      Bughunter Media
         html/css
         html/images
         html/scripts

      Bughunter js
         html/scripts/views/Bases.js                  - See details for js in Architecture section
         html/scripts/views/BHViewComponent.js
         html/scripts/views/BHViewCollection.js
         html/scripts/views/BughunterPage.js
         html/scripts/views/ConnectionsComponent.js
         html/scripts/views/DataAdapterCollection.js
         html/scripts/views/VisualizationCollection.js
         html/scripts/views/HelpPage.js

      Admin Application JS                
         html/scripts/bughunter/app.js
         html/scripts/bughunter/model.js
         html/scripts/bughunter/utils.js
         html/scripts/bughunter/views.js

      Admin Application Styles
         html/style/...                               - CSS for admin application



## Architecture
### Webservice
#### Bughunter Views

The primary data service for data views is found in bughunter/views.py
in the method get_bhview.  This method maps the incoming view name to
an adapter found in the datastructure VIEW_ADAPTERS to a function
reference that knows how to build the data for that view.  An example
url would look like:

  /bughunter/api/views/crash_detail_st

Where crash_detail_st is the view name.  A function decorator provides
get_bhview with all the data needed to retrieve the view data. It passes
this data on to the appropriate view adapter.

A datasource datahub object is used for all database queries.  This
object is stored in settings.DHUB.  It provides a complete interface for
building SQL dynamically, storing it in a json structure in a separate
file, and executing/retrieving the data from the database.  The datasource
module used for this can be found at https://github.com/jeads/datasource.

### JS
#### Class Structures

The javascript that implements the user interface is constructed
using a page/component/collection pattern thingy... whatever that means.  
This was found very useful in separating out the required functionality,
below is a brief definition of what that means in bughunter.

**Page**

Manages the DOM ready event, implements any top level initialization
that's required for the page.  An instance of the page class is the
only global variable that other components can access, if they're playing
nice.  The page class instance is responsible for instantiating components
and storing them in attributes.  The page class also holds any data structures
that need to be globally accessible to component classes.

**Component**

Contains the public interface of the component.  A component can
encapsulate any functional subset/unit provided in a page.  The
component will typically have an instance of a View and Model class.  
The component class is also responsible for any required event binding.

**View**

A component's view class manages interfacing with the DOM. Any CSS class
names or HTML id's are defined as attributes of the view.  Any HTML element
modification is controlled with this class.

**Model**

A component's model manages any asynchronous data retrieval and large data
structure manipulation.

**Collection**

A class for managing a collection of Components or classes of any type.  
A collection can also have a model/view if appropriate.

#### Bughunter Client Application (python/sisyphus/webapp/html/scripts/views/)

This is not a complete file or class listing but is intended to give a top level
description of the design pattern thingy of the bughunter javascript and what the
basic functional responsibility of the pages/components/collections are.

    BughunterPage.js

       BughunterPage Class - Manages the DOM ready event, component initialization, and
                             retrieval of the views.json structure that is used by different
                             components.

    Bases.js

       Design Pattern Base Classes - Contains the base classes for Page, Component,
                                     Model, View etc...

    BHViewComponent.js

       BHViewComponent Class - Encapsulates the behavior of a single data view using a model/view and  
                               provides a public interface for data view functionality.  Manages
                               event binding and registration.

       BHViewView Class - Encapsulates all DOM interaction required by a data view.

       BHViewModel Class - Encapsulates asynchronous server communication and data structure
                           manipulation/retrieval.

    BHViewCollection.js

      BHViewCollection Class - Manages operations on a collection of data views using a model/view
                               including instantiating view collections.  

      BHViewCollectionView Class - Encapsulates all DOM interaction required by the collection.

      BHViewCollectionModel Class - Provides an interface to the datastructures holding all data
                                    views and their associated parent/child relationships.
    DataAdapterCollection.js

      DataAdapterCollection Class - Collection of BHViewAdapter class instances.

      BHViewAdapter Class - Base class for all BHViewAdapters.  Manages shared view
                            idiosyncratic behavior like what fields go in the
                            control panel and how to populate/retrieve them for
                            signaling behavior.

      CrashesAdapter Class - Derived class of BHViewAdapter.  Encapsulates unique
                             behavior for crash data views.

      UrlAdapter Class - Derived class of BHViewAdapter. Encapsulates unique behavior for
                         views containing URL summaries.
