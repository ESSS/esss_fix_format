===============================
esss_fix_format
===============================


.. image:: https://img.shields.io/travis/ESSS/esss_fix_format/master.svg
        :target: https://travis-ci.org/ESSS/esss_fix_format


Simple code formatter and pre-commit checker used internally by ESSS.

* Imports sorted using `isort <https://pypi.python.org/pypi/isort>`_;
* Trim right spaces;
* Expand tabs;


Install
-------

.. code-block:: sh

    conda install esss_fix_format

Note:

If executed from the root environment (or another environment) isort could classify wrongly some modules,
so, you should install and run it from the same environment you're using for your project.


Usage
-----

Use ``fix-format`` (or ``ff`` for short) to reorder imports and format source code automatically.

1. To format files and/or directories::

    fix-format <file1> <dir1> ...


2. Format only modified files in Git::

    fix-format --commit

   Or more succinctly::

    ff -c


Migrating a project to use fix-format
-------------------------------------

Follow this steps to re format an entire project and start using the pre-commit hook:

1. You should have ``ff`` available in your environment already:

    .. code-block:: sh

        $ ff --help
        Usage: ff-script.py [OPTIONS] [FILES_OR_DIRECTORIES]...

          Fixes and checks formatting according to ESSS standards.

        Options:
          -k, --check   Check if files are correctly formatted.
          --stdin       Read filenames from stdin (1 per line).
          -c, --commit  Use modified files from git.
          --git-hooks   Add git pre-commit hooks to the repo in the current dir.
          --help        Show this message and exit.


2. For each file you don't want imports reordered add ``isort:skipfile`` to the docstring:

    .. code-block:: python

        """
        isort:skip_file
        """

   Commit using ``-n`` to skip the current hook.

3. If there are any sensitive imports in your code which you wouldn't like to ``ff`` to touch, use
   a comment to prevent ``isort`` from touching it:

    .. code-block:: python

        ConfigurePyroSettings()  # must be called before importing Pyro4
        import Pyro4  # isort:skip

4. If you want to use ``clang-format`` to format C++ code, you should copy the ``.clang-format``
   file from ``esss-fix-format`` to the root of your project. This is optional for now in order
   to allow incremental changes (if this file is not present, the legacy C++ formatter will
   be used):

    .. code-block:: sh

        $ cd /path/to/repo/root
        $ curl -O https://raw.githubusercontent.com/ESSS/esss_fix_format/master/.clang-format

5. Execute:

    .. code-block:: sh

        $ cd /path/to/repo/root
        $ ff .

   After it completes, make sure there are no problems with the files:

    .. code-block:: sh

        $ ff . --check

   .. note::
        if the check fails, try running it again; there's a rare
        `bug in isort <https://github.com/timothycrosley/isort/issues/460>`_ that might
        require to run ``ff /path/to/repo/root`` twice.

   Commit:

    .. code-block:: sh

        $ git commit -anm "Apply fix-format on all files" --author="fix-format"

6. Push and run your branch on CI.

7. If all goes well, it's possible to install pre-commit hooks by using ``ff --git-hooks`` so
   that any commit will be checked locally before commiting.

8. Profit!


Developing (conda)
------------------

Create a conda environent (using Python 3 here) and install it in development mode.
Make sure you have conda configured to use ``conda-forge`` and ``esss`` conda channels.

.. code-block:: sh

    $ conda install -n base conda-devenv
    $ conda devenv
    $ source activate esss-fix-format-py36
    $ pytest

When implementing changes, please do it in a separate branch and open a PR.

Licensed under the MIT license.
