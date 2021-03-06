import os
import subprocess
import sublime, sublime_plugin
import threading
import sys
import time
import shutil

from zipfile import ZipFile
from .sexp import parse_sexp

# Build a local version of find_targets -- This will allow us to interface with the existing OCaml
base_directory = sublime.cache_path()
local_dst = os.path.join(base_directory, "find_targets")
try:
	shutil.rmtree(local_dst)
except FileNotFoundError:
	# That's ok, if the tree doesn't exist we don't need to remove it
	pass

self_directory = os.path.dirname(__file__)

# Are we running as a compiled package
if self_directory.split(".")[-1] == "sublime-package":
	self_package = ZipFile(self_directory)
	for file in self_package.namelist():
		if file.startswith("find_targets"):
			self_package.extract(file, local_dst)
# Or are we loaded in as a directory
else:
	local_src = os.path.join(self_directory, "find_targets")
	shutil.copytree(local_src, local_dst)

find_targets_exe = os.path.join(base_directory, "_build", "default", "find_targets", "find_targets.exe")

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
		Find_targets_builder.build_lock.release()

class Find_targets:
	def __init__(self, path=os.path.join(base_directory,".")):
		self.path=os.path.abspath(path)

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
	def __init__(self, window):
		threading.Thread.__init__(self, name="JBuilder Status")
		self.terminator = {"end" : False}
		self.view = window.active_view()
		self.state = 0

	def run(self):
		while True:
			if self.terminator["end"]:
				return
			states = [
				"[<==>    ]",
				"[ <==>   ]",
				"[  <==>  ]",
				"[   <==> ]",
				"[    <==>]",
				"[>    <==]",
				"[=>    <=]",
				"[==>    <]",
			]

			self.view.set_status("JBuilder", "JBuilder: "+states[self.state])
			self.state += 1
			self.state %= len(states)
			time.sleep(0.05)

	def stop(self, success):
		self.terminator["end"] = True
		if (success):
			self.view.set_status("JBuilder", "JBuilder: Succeeded")
		else:
			self.view.set_status("JBuilder", "JBuilder: Failure")

class SingleBuilder(threading.Thread):
	def __init__(self, window, working_directory, targets, on_done):
		threading.Thread.__init__(self, name=("JBuilder targets {}".format(targets)))
		self.working_directory = working_directory
		self.targets = targets
		self.on_done = on_done
		self.window = window

	def run_in_background(self):
		self.status = JbuilderStatus(self.window)
		self.status.start()
		result = self.start()

	def run (self):
		os.chdir(self.working_directory)
		procs = []
		error = ""
		for target in self.targets:
			if not target:
				continue
			proc = subprocess.Popen (["jbuilder", "build", target], 
				stdout=subprocess.PIPE, 
				stderr=subprocess.PIPE, 
				cwd=self.working_directory)
			return_code = proc.wait()
			if return_code != 0:
				error += "{}: {}\n\n".format(target, proc.stderr.read().decode("utf-8"))

		success = True
		if error:
			self.window.run_command("jbuilder_show_compilation_errors", {"args": {"text": error}})
			success = False

		self.status.stop(success)

class JbuilderShowCompilationErrors(sublime_plugin.TextCommand):
	def run(self, edit, args):
		sig_text = args["text"]
		window = self.view.window()

		output = window.create_output_panel("jbuilder-errors")
		full_region = sublime.Region(0, output.size())
		output.replace(edit, full_region, sig_text)

		output.sel().clear()
		window.run_command("show_panel", {"panel": "output.jbuilder-errors"})

def get_build_targets_from_environment(path, window):
	if path == None:
		sublime.error_message("Please save file before building")
		return 
	path = "/".join(path.split("/")[:-1])

	if len(window.folders()) > 0:
		working_directory = window.folders()[0]
	else:
		working_directory = find_dot_sublime_targets(path)
		if working_directory == None:
			working_directory = path
	targets_file = os.path.join(working_directory, ".sublime-targets")
	contents = None
	try:
		with open(targets_file, "r+") as targets_fd:
			contents = targets_fd.read()
	except FileNotFoundError:
		pass
	return (working_directory, targets_file, contents)

def prompt_add_target(targets_file, window, client_on_done):
	folder = window.folders()[0] if len(window.folders()) > 0 else "."
	find_targets = Find_targets(path=folder)
	targets = [y for (x,y) in find_targets.list()]

	def on_done (idx):
		if (idx < 0):
			return
		with open(targets_file, "a+") as targets_fd:
			targets_fd.write(targets[idx]+"\n")
		with open(targets_file, "r") as targets_fd:
			client_on_done(targets_fd.read())

	window.show_quick_panel(targets, on_done)

def prompt_remove_target(targets_file, contents, window, client_on_done):
	if contents == None:
		sublime.error_message("No targets defined")
	targets = contents.strip().split("\n")

	def on_done (idx):
		if (idx < 0):
			return
		with open(targets_file, "w+") as targets_fd:
			targets_fd.write("\n".join(targets[:idx]+targets[idx+1:]))
		with open(targets_file, "r") as targets_fd:
			client_on_done(targets_fd.read())

	window.show_quick_panel(targets, on_done)

def build_targets(window, working_directory, contents):
	if contents == None:
		sublime.error_message("Fatal: Cannot find .sublime-targets in directory {}".format(working_directory))
	builder = SingleBuilder(window, working_directory, contents.split("\n"), 3)
	builder.run_in_background()

class JbuilderCmd(sublime_plugin.WindowCommand):
	def __init__(self, window):
		self.window = window
		self.view = window.active_view()

	def run(self, cmd=""):
		path = cmd
		(working_directory, targets_file, contents) = get_build_targets_from_environment(path, self.window)
		
		def on_done(contents):
			build_targets(self.window, working_directory, contents)

		if not contents:
			prompt_add_target(targets_file, self.window, on_done)
		else:
			build_targets(self.window, working_directory, contents)


class JbuilderAddTarget(sublime_plugin.WindowCommand):
	def __init__(self, window):
		self.window = window
		self.view = window.active_view()

	def run(self):
		path = "/".join(self.view.file_name().split("/")[:-1])
		(working_directory, targets_file, contents) = get_build_targets_from_environment(path, self.window)

		def on_done(contents):
			pass

		prompt_add_target(targets_file, self.window, on_done)

class JbuilderRemoveTarget(sublime_plugin.WindowCommand):
	def __init__(self, window):
		self.window = window
		self.view = window.active_view()

	def run(self):
		path = "/".join(self.view.file_name().split("/")[:-1])
		(working_directory, targets_file, contents) = get_build_targets_from_environment(path, self.window)

		def on_done(contents):
			pass

		prompt_remove_target(targets_file, contents, self.window, on_done)



