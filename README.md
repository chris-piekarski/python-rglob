The final Python 2 package version is 1.4  
Python 2 PyPi: https://pypi.org/project/rglob/1.4/  
Python 3 PyPi: https://pypi.org/project/rglob/1.7/  

pip install rglob  

Example:

import rglob  
pyFiles = rglob.rglob("/", "\*.py")  
pyFiles = rglob.rglob_("\*.py")  

Troubleshooting:

git clone git://github.com/chris-piekarski/python-rglob.git  
pip install lettuce  
cd ~/python-rglob  
lettuce
