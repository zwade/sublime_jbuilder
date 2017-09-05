import os
import subprocess
import sublime, sublime_plugin
import threading
import sys

base_directory = os.path.dirname(os.path.realpath(__file__))
find_targets_exe = os.path.join(base_directory, "_build", "default", "find_targets", "find_targets.exe")

# Weird hacks to avoid sublime caching an old version
if sys.version_info.minor < 3:
	from sexp import parse_sexp
else:
	if sys.version_info.minor < 4:
	    from imp import reload
	else:
	    from importlib import reload
	if base_directory not in sys.path:
	    sys.path.append(base_directory)

	import sexp
	reload(sexp)

	from sexp import parse_sexp

class Find_targets_builder(threading.Thread):
	build_lock = threading.Lock()
	def needs_reload(self, force=False):
		return (force 
			or not os.path.isfile(find_targets_exe)
			or ("BUILD_ON_RELOAD" in os.environ and os.environ["BUILD_ON_RELOAD"]))

	def run(self):
		Find_targets_builder.build_lock.acquire()
		os.chdir(base_directory)
		print("Rebuilding find_targets in directory {}".format(base_directory))
		proc = subprocess.Popen (["jbuilder", "build", "find_targets/find_targets.exe"], 
			stdout=subprocess.PIPE, 
			stderr=subprocess.PIPE, 
			cwd=base_directory, 
			env={"PATH": os.environ["PATH"]})
		return_code = proc.wait()
		if return_code != 0:
			print("jbuilder failed with:")
			print(proc.stderr.read().decode("utf-8"))
		else:
			print("jbuilder succeeded")
		Find_targets_builder.build_lock.release()

class Find_targets:
	def __init__(self, path=os.path.join(base_directory,"..")):
		self.path=os.path.abspath(path)
		print(self.path)

	def relativize(self, new_path):
		my_path  = self.path.split("/")
		new_path = new_path.split("/")
		print (my_path, new_path)
		
		to_traverse = range(min(len(my_path), len(new_path)))
		for i in to_traverse:
			if my_path[0] == new_path[0]:
				my_path = my_path[1:]
				new_path = my_path[1:]
			else:
				break

		return [".." for _i in my_path] + new_path


	def list(self):
		proc = subprocess.Popen([find_targets_exe, "list", "-root", self.path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		proc.wait()
		result = proc.stdout.read().decode("utf-8")
		mapping = parse_sexp(result)
		targets = []
		for (path, target_names) in mapping:
			relative_path = self.relativize(path)
			print("Path: {}, Rel path: {}".format(path, relative_path))
			for target_name in target_names:
				targets.append(os.path.join(*(relative_path+[target_name])))
		print(targets)


def reload_if_needed(force=False):
	target_builder = Find_targets_builder()
	if target_builder.needs_reload(force):
		target_builder.start()

reload_if_needed(force=True)

class JbuilderCmd(sublime_plugin.WindowCommand):
	def run(self):
		targets = Find_targets()
		targets.list()