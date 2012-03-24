from lettuce import *
import rglob
import tempfile
import os

world.root = None
world.dirs = []

@step('I create a root directory')
def create_root_dir(step):
	if world.root == None:
		world.root = tempfile.mkdtemp(suffix='_rglob', prefix='root_')
		
@step('I create (\d+) subdirectories in each directory')
def create_subdirectores(step, num_of_sub_dirs):
	subdirs = []
	num_dirs = int(num_of_sub_dirs)
	if len(world.dirs) == 0:
		for t in range(0,num_dirs):
			subdirs.append(tempfile.mkdtemp(prefix='subdir_', suffix='_rglob', dir=world.root))
	else:
		for root_dir in world.dirs:
			for n in range(num_dirs):
				subdirs.append(tempfile.mkdtemp(prefix='subdir_', suffix='_rglob', dir=root_dir))
			
	world.dirs.extend(subdirs)
	
@step('I create (\d+) (.*) files in each directory')
def create_files(step, num_of_files, file_type ):
	for d in world.dirs:
		for n in range(0,int(num_of_files)):
			contents = "{}: auto generated rglob lettuce test file".format(n)
			file_name = tempfile.mktemp(prefix='rglob_test_file', suffix=file_type, dir=d)
			_create_file(file_name, contents)
		
def _create_file(name, contents):
	with open(name, 'w') as f:
		f.write(contents)
	
@step('I find (\d+) total directories')
def find_directories(step, expected_num_of_dirs):
	x = rglob.rglob(world.root, "*_rglob")
	assert len(x) == int(expected_num_of_dirs), \
		"Found {} directories".format(len(x))
		
@step('I find (\d+) total (.*) files')
def find_files(step, expected_num_of_files, file_type):
	x = rglob.rglob(world.root, "*{}".format(file_type))
	assert len(x) == int(expected_num_of_files), \
		"Found {} files".format(len(x))
		
@step('I delete all')
def delete_all_directories(step):
	x = rglob.rglob(world.root, "*")
	x.sort(reverse=True)
	for d in x:
		if os.path.isdir(d):
			os.rmdir(d)
		else:
			os.remove(d)
	del world.dirs
	world.dirs = []