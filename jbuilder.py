import os
import subprocess
import sublime, sublime_plugin
import threading
import sys
import time

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
	def __init__(self, path=os.path.join(base_directory,".")):
		self.path=os.path.abspath(path)
		print(self.path)

	def relativize(self, new_path):
		my_path  = self.path.split("/")
		new_path = new_path.split("/")

		to_traverse = range(min(len(my_path), len(new_path)))
		for i in to_traverse:
			if my_path[0] == new_path[0]:
				my_path  = my_path[1:]
				new_path = new_path[1:]
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
			for target_name in target_names:
				rel_path = os.path.join(*(relative_path+[target_name]))
				abs_path = os.path.join(path, target_name)
				targets.append((abs_path, rel_path))
		return targets


def reload_if_needed(force=False):
	target_builder = Find_targets_builder()
	if target_builder.needs_reload(force):
		target_builder.start()

def find_dot_sublime_targets (path):
	if os.path.isfile(os.path.join(path, ".sublime-targets")):
		return path
	if path == "/":
		return None
	return find_dot_sublime_targets (os.path.dirname(path))


reload_if_needed(force=True)

class JbuilderStatus(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self, name="JBuilder Status")
		self.terminator = {"end" : False}

	def run(self):
		while True:
			if self.terminator["end"]:
				return
			time.sleep(2)

	def stop(self):
		self.terminator["end"] = True

class SingleBuilder(threading.Thread):
	def __init__(self, working_directory, targets, on_done):
		threading.Thread.__init__(self, name=("JBuilder targets {}".format(targets)))
		self.working_directory = working_directory
		self.targets = targets
		self.on_done = on_done

	def run_in_background(self):
		status = JbuilderStatus()
		result = self.start()
		status.stop()
		print(result)

	def run (self):
		os.chdir(self.working_directory)
		procs = []
		for target in self.targets:
			proc = subprocess.Popen (["jbuilder", "build", target], 
				stdout=subprocess.PIPE, 
				stderr=subprocess.PIPE, 
				cwd=base_directory)
			procs.append((target, proc))
		for (target, proc) in procs:
			return_code = proc.wait()
			if return_code != 0:
				print("jbuilder failed with:")
				print(proc.stderr.read().decode("utf-8"))
			else:
				print("jbuilder succeeded for {}".format(target))


class JbuilderCmd(sublime_plugin.WindowCommand):
	def __init__(self, window):
		self.window = window

	def run(self, cmd):
		path = cmd
		if len(self.window.folders()) > 0:
			working_directory = self.window.folders()[0]
		else:
			if path[-1] == "/":
				path = path[:-1]
			base_dir = find_dot_sublime_targets(path)
			if base_dir == None:
				base_dir = path
			working_directory = base_dir
		targets_file = os.path.join(working_directory, ".sublime-targets")

		def on_done (idx):
			if (idx < 0):
				return
			open(targets_file, "a+").write(targets[idx]+"\n")
			self.window.open_file(targets_file)
			builder = SingleBuilder(working_directory, [targets[idx]], 3)
			builder.run_in_background()

		folder = self.window.folders()[0] if len(self.window.folders()) > 0 else "."
		find_targets = Find_targets(path=folder)
		targets = [y for (x,y) in find_targets.list()]

		contents = open(targets_file, "r+").read()
		print(contents)
		if not contents:
			self.window.show_quick_panel(targets, on_done)
		else:
			builder = SingleBuilder(working_directory, contents.split("\n"), 3)
			builder.run_in_background()