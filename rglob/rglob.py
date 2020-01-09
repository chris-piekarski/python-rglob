"""
Recursive Glob Module
Methods:
	rglob(base, pattern)
	rglob_(pattern)
	lcount(base, pattern, func=lambda x : True)
	tsize(base, pattern, func=lambda x : (x / math.pow(2.0, 20))
"""
import math
import glob
import os

kilobytes = lambda x : (x / math.pow(2.0, 10.0))
megabytes = lambda x : (x / math.pow(2.0, 20.0))
gigabytes = lambda x : (x / math.pow(2.0, 30.0))
terabytes = lambda x : (x / math.pow(2.0, 40.0))

def _getDirs(base):
	return [x for x in glob.iglob(os.path.join( base, '*')) if os.path.isdir(x) ]

def _count(files, func):
	lines = 0
	for f in files:
		lines += sum([1 for l in open(f) if func(l)])
	return lines

def _sum(files):
	total_size = 0
	for f in files:
		if not os.path.isdir(f):
			total_size += os.path.getsize(f)
	return total_size


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
	all_files = rglob(base, pattern)
	return _count(all_files, func)

def tsize(base, pattern, func = megabytes ):
	""" Sums and returns the total size of every file found from glob(base,pattern)
		Params:
			base - root directory to start the search
			pattern - pattern for glob to match (i.e '*.py')
			func - unit prefix conversion function
				example: lambda x : (x / math.pow(2.0,20.0)) # megabytes
				default: func = megabytes 
	""" 
	all_files = rglob(base, pattern)
	total_size = _sum(all_files)
	return func(total_size)

if __name__ == "__main__":
	#filter out empty lines and comments
	filterFunc = lambda x : True if (len(x.strip()) and x.strip()[0] != '#') else False
    
	pyFiles = rglob(os.path.dirname(__file__), "*.py")
	print(" {} total lines".format(_count(pyFiles, filterFunc)))
	
	pyFiles_ = rglob_("*.py")
	print(" {} total lines".format(_count(pyFiles_, filterFunc)))
	print(" {} total lines".format(lcount(os.path.dirname(__file__), "*.py", filterFunc)))
	
