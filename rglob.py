import glob
import os
 
def _getDirs(base):
    return [x for x in glob.iglob(os.path.join( base, '*')) if os.path.isdir(x) ]
 
def rglob(base, pattern):
    """ recursive glob starting in specified directory """
    list = []
    list.extend(glob.glob(os.path.join(base,pattern)))
    dirs = _getDirs(base)
    if len(dirs):
        for d in dirs:
            list.extend(rglob(os.path.join(base,d), pattern))
    return list

def rglob_(pattern):
    """ performs a recursive glob in the current working directory """
    return rglob(os.getcwd(), pattern)

if __name__ == "__main__":
    pyFiles = rglob(os.path.dirname(__file__), "*")
    print pyFiles
    
    pyFiles_ = rglob_("*")
    print pyFiles_