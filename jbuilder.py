import os
import subprocess
import sublime, sublime_plugin
import threading

base_directory = os.path.dirname(os.path.realpath(__file__))
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
		else:
			print("jbuilder succeeded")
		Find_targets_builder.build_lock.release()

class Find_targets:
	def list(self, path="."):
		proc = subprocess.Popen([find_targets_exe, "list", "-root", base_directory], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		proc.wait()
		print(proc.stdout.read().decode("utf-8"))

def reload_if_needed(force=False):
	target_builder = Find_targets_builder()
	if target_builder.needs_reload(force):
		target_builder.start()

reload_if_needed(force=True)

class JbuilderCmd(sublime_plugin.WindowCommand):
	def run(self):
		targets = Find_targets()
		targets.list("..")