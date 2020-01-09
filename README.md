This file is part of the python 'rglob' package.
Copyright (C) 2011 by 
Christopher Piekarski <chris@cpiekarski.com>
PyPi: http://pypi.python.org/pypi/rglob/

The 'rglob' module is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

The 'rglob' module is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with the 'rglob' module.  If not, see <http://www.gnu.org/licenses/>.

Example:

import rglob
pyFiles = rglob.rglob("/", "*.py")
pyFiles = rglob.rglob_("*.py")

Troubleshooting:

I tried but was unable to test this Python27 module on every OS under every possible
scenario :-) Since the publication I have received one bug report regarding rglob
not properly finding sub-directories. I have used this module heavily and haven't run into
any issues. If you do its most likely environment related so be sure to run the module 
lettuce test before submitting a patch.

git clone git://github.com/chris-piekarski/python-rglob.git	
pip install lettuce
cd ~/python-rglob
lettuce