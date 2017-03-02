=======
History
=======


1.4.1
-----

* Fix support for filenames in pattern (such as `CMakeLists.txt`), when in subdirectories.

1.4.0
-----

* Add support for CMake files (`*.cmake`, `CMakeLists.txt`).

1.3.0
-----

* Add support for Cython files (`*.pyx`, `*.pxd`).

1.2.4
-----

* Fix `ff -c`/`ff --commit` in Python 3.

1.2.3
-----

* Force to always use parentheses on multi-line imports.

1.2.2
-----

* Workaround for isort bug where some stdlib modules are not recognized as such because of a
  non-standard Python location.

1.2.1
-----

* Fixed bug where EOL wasn't preserved in files affected by isort.


1.2.0
-----

* Add "-k" shortcut for "--check".

* Display a summary of files which skipped checks.

* Fixed error when an entire file was skipped due to a "isort:skip_file"
  instruction on the docstring.

1.1.1
-----

* Display error summary at the end in case some error happens when fixing files.

* Fix bug when a file contained a single empty line.

1.1.0
-----

* Add support for passing directories in the command line.

* No longer check files for a specific end-of-line.

* Fixed `#1`_: `--commit` option was not considering git root directory when listing files.

.. _`#1`: https://github.com/ESSS/esss_fix_format/issues/1

1.0.0
-----

* First version.
