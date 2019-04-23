#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Runs the webapp in a docker container for local development.

set -e

echo "******************************************************************"
echo "Running webapp in local dev environment."
echo "Connect with your browser using: http://localhost:8000/ "
echo "******************************************************************"

# cd into the webapp directory
cd /app/sisyphus/webapp

# Apply database migrations
python manage.py migrate

# Start the server
python manage.py runserver 0.0.0.0:8000
