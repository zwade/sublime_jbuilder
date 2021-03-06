# Sublime JBuilder

## About

Sublime JBuilder is a build system for sublime that integrates into the existing build systems. Its still a work in progress, but you can try out the current version by adding `https://github.com/zwade/sublime_jbuilder.git` as a repository in Package Control, and then installing `jbuilder`. 

Note, you will also need to have `opam` installed. Once you do, run `opam install core async jbuilder` to install all of the dependencies you need. You will also need to add `~/.opam/X.X.X/bin` to your path, otherwise Sublime won't be able to find the executable.

## Features

Sublime JBuilder currently supports the following features

 - [x] Automatic target detection
 - [x] Support for building multiple targets at once
 - [x] An easy interface for managing current build targets
 
Upcoming Features

 - [ ] A (quiet) build on save option
 - [ ] File-level build options (instead of directory-level)
 - [ ] Better error handling

## Contributing

If there are features that you would like added, feel free to add an issue. Otherwise, I will gladly accept outside code

## Credits

Zach Wade (@zwad3)
