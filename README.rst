===============================
esss_fix_format
===============================

.. image:: https://github.com/ESSS/esss_fix_format/workflows/linux/badge.svg
  :target: https://github.com/ESSS/esss_fix_format/actions?query=workflow%3Alinux

.. image:: https://github.com/ESSS/esss_fix_format/workflows/windows/badge.svg
  :target: https://github.com/ESSS/esss_fix_format/actions?query=workflow%3Awindows

Simple code formatter and pre-commit checker used internally by ESSS.

* Imports sorted using `isort <https://pypi.python.org/pypi/isort>`_
* Trim right spaces
* Expand tabs
* Formats Python code using `PyDev Code Formatter <https://github.com/fabioz/PyDev.Formatter>`_ or `black <https://github.com/python/black>`__
* Formats C++ code using `clang-format <https://clang.llvm.org/docs/ClangFormat.html>`_ if a ``.clang-format`` file is available


Install
-------

.. code-block:: sh

    conda install esss_fix_format

Note:

If executed from the root environment (or another environment) isort will classify modules incorrectly,
so you should install and run it from the same environment you're using for your project.


Usage
-----

Use ``fix-format`` (or ``ff`` for short) to reorder imports and format source code automatically.

1. To format files and/or directories::

    fix-format <file1> <dir1> ...


2. Format only modified files in Git::

    fix-format --commit

   Or more succinctly::

    ff -c


.. _black:

Options
-------

Options for ``fix-format`` are defined in the section ``[tool.esss_fix_format]]`` of a ``pyproject.toml`` file. The
TOML file should be placed in an ancestor directory of the filenames passed on the command-line.


Exclude
^^^^^^^

A list of file name patterns to be excluded from the formatting. Patterns are matched using python ``fnmatch``:

   .. code-block:: toml

    [tool.esss_fix_format]
    exclude = [
        "src/generated/*.py",
        "tmp/*",
    ]


Black
^^^^^

Since version ``2.0.0`` it is possible to use `black <https://github.com/python/black>`__ as the
code formatter for Python code.

``fix-format`` will use ``black`` automatically if it finds a ``[tool.black]`` section declared in ``pyproject.toml``
file.

See "Converting master to black" below for details.

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

5. If you want to use ``black`` to format Python code, add a ``pyproject.toml`` to the root of
   your repository; an example can be found in "Converting master to black" below.

6. Activate your project environment:

    .. code-block:: sh

            $ conda activate myproject-py36

7. Execute:

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

        $ git commit -anm "Apply fix-format on all files" --author="fix-format <fix-format@esss.com.br>"

8. Push and run your branch on CI.

9. If all goes well, it's possible to install pre-commit hooks by using ``ff --git-hooks`` so
   that any commit will be checked locally before commiting.

10. Profit! 💰

Migrating from PyDev formatter to black
---------------------------------------

Migrating an existing code base from a formatter to another can be a bit of pain. This steps will
help you diminish that pain as much as possible.


Converting ``master`` to black
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The first step is converting your ``master`` branch to black.

1. Add a ``pyproject.toml`` project with this contents:

   .. code-block:: toml

      [tool.black]
      line-length = 100
      skip-string-normalization = true

2. If your project doesn't have a ``.isort.cfg`` file, create one at the project's *repository*
   root with the same contents as `the one <https://github.com/ESSS/esss_fix_format/blob/master/.isort.cfg>`_
   in the root of this repository.

3. Run the ``upsert-isort-config`` task to update it (it should be run regularly, specially when adding new
   dependencies to internal projects, known as "first party" dependencies); *or*, if the project needs special
   configurations due to dual package and source modes, add these lines (and do not run ``upsert-isort-config``):

   .. code-block:: ini

      [settings]
      profile=black
      no_sections=True
      force_alphabetical_sort=True

   This will use black-like grouping, and clump imports together regardless if they are standard library,
   third party, or local. This avoids getting different results if you have a different environment activated,
   or commiting from an IDE.

4. Commit, and save the commit hash, possible in a task that you created for this conversion:

   .. code-block:: sh

      $ git commit -anm "Add configuration files for black"


5. Execute on the root of the repository:

   .. code-block:: sh

      $ fix-format .

6. Ensure everything is fine:

   .. code-block:: sh

      $ fix-format --check .

   If you **don't** see any "reformatting" messages, it means everything is formatted correctly.

7. Commit and then open a PR:

   .. code-block:: sh

      $ git commit -anm "Convert source files to black" --author="fix-format <fix-format@esss.com.br>"


Porting an existing branch to black
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here we are in the situation where the ``master`` is already blacken, and you want
to update your branch. There are two ways, and which way generates less conflicts really
depends on the contents of the source branch.

merge -> Fix format
'''''''''''''''''''

1. Merge with the target branch, resolve any conflicts and then commit normally.

2. Execute ``fix-format`` in the root of your repository:

   .. code-block:: sh

       $ fix-format .

   This should only change the files you have touched in your branch.

3. Commit and push:

   .. code-block:: sh

     $ git commit -anm "Convert source files to black" --author="fix-format <fix-format@esss.com.br>"


Fix format -> merge
'''''''''''''''''''

1. Cherry-pick the commit you saved earlier on top of your branch.

2. Execute ``fix-format`` in the root of your repository:

   .. code-block:: sh

       $ fix-format .

   (In very large repositories, this will be a problem on Windows because of the command-line size, do it
   in chunks).

3. Fix any conflicts and then commit:

   .. code-block:: sh

     $ git commit -anm "Convert source files to black" --author="fix-format <fix-format@esss.com.br>"


Developing
----------

Create a conda environment (using Python 3 here) and install it in development mode.

**Make sure you have conda configured to use ``conda-forge`` and ``esss`` conda channels.**

.. code-block:: sh

    $ conda install -n base conda-devenv
    $ conda devenv
    $ source activate esss-fix-format-py36
    $ pre-commit install
    $ pytest

When implementing changes, please do it in a separate branch and open a PR.

Releasing
^^^^^^^^^

The release is done internally at ESSS using our `conda-recipes` repository.


License
-------

Licensed under the MIT license.
