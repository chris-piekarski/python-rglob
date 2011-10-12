import glob
import os

def _getDirs(base):
	return [x for x in glob.iglob(os.path.join( base, '*')) if os.path.isdir(x) ]

def _count(files):
	lines = 0
	for f in files:
		lines += sum(1 for l in open(f))
	return lines


def rglob(base, pattern):
	""" recursive glob starting in specified directory """
	flist = []
	flist.extend(glob.glob(os.path.join(base,pattern)))
	dirs = _getDirs(base)
	if len(dirs):
		for d in dirs:
			flist.extend(rglob(os.path.join(base,d), pattern))
	return flist

def rglob_(pattern):
	""" performs a recursive glob in the current working directory """
	return rglob(os.getcwd(), pattern)

def lcount(base, pattern):
	allFiles = rglob(base, pattern)
	return _count(allFiles)

if __name__ == "__main__":
	pyFiles = rglob(os.path.dirname(__file__), "*.py")
	print pyFiles, " {} total lines".format(_count(pyFiles))
	
	pyFiles_ = rglob_("*.py")
	print pyFiles_, " {} total lines".format(_count(pyFiles))