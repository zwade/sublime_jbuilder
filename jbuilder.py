import os
import subprocess
import sublime, sublime_plugin

base_directory = os.path.dirname(os.path.realpath(__file__))
find_targets_exe = os.path.join(base_directory, "_build", "default", "find_targets", "find_targets.exe")

def reload_if_needed(force=False):
	if (force 
			or not os.path.isfile(find_targets_exe)
			or ("BUILD_ON_RELOAD" in os.environ and os.environ["BUILD_ON_RELOAD"])):
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


reload_if_needed()

class JbuilderCmd(sublime_plugin.WindowCommand):
	def run(self, cmd):
		print("hello")
		pass