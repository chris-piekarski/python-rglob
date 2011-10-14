"""
Recursive Glob Module
Methods:
	rglob(base, pattern)
	rglob_(pattern)
	lcount(base, pattern, func=lambda x : True)
"""
import glob
import os

def _getDirs(base):
	return [x for x in glob.iglob(os.path.join( base, '*')) if os.path.isdir(x) ]

def _count(files, func):
	lines = 0
	for f in files:
		lines += sum([1 for l in open(f) if func(l)])
	return lines


def rglob(base, pattern):
	""" Recursive glob starting in specified directory """
	flist = []
	flist.extend(glob.glob(os.path.join(base,pattern)))
	dirs = _getDirs(base)
	if len(dirs):
		for d in dirs:
			flist.extend(rglob(os.path.join(base,d), pattern))
	return flist

def rglob_(pattern):
	""" Performs a recursive glob in the current working directory """
	return rglob(os.getcwd(), pattern)

def lcount(base, pattern, func = lambda x : True):
	""" Counts the number of lines in each file found matching pattern.
		Params:
			base - root directory to start the search
			pattern - pattern for glob to match (i.e '*.py')
			func - boolean filter function
				example: lambda x : True if len(x.strip()) else False #don't count empty lines
				default: lambda x : True
	"""
	allFiles = rglob(base, pattern)
	return _count(allFiles, func)

if __name__ == "__main__":
	#filter out empty lines and comments
	filterFunc = lambda x : True if (len(x.strip()) and x.strip()[0] != '#') else False
    
	pyFiles = rglob(os.path.dirname(__file__), "*.py")
	print " {} total lines".format(_count(pyFiles, filterFunc))
	
	pyFiles_ = rglob_("*.py")
	print " {} total lines".format(_count(pyFiles_, filterFunc))
	print " {} total lines".format(lcount(os.path.dirname(__file__), "*.py", filterFunc))
	