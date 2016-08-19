===============================
esss_fix_format
===============================


.. image:: https://img.shields.io/travis/ESSS/esss_fix_format/master.svg
        :target: https://travis-ci.org/esss/esss_fix_format


Simple code formatter and pre-commit checker used internally by ESSS.

* Imports sorted using `isort <https://pypi.python.org/pypi/isort>`_;
* Trim right spaces;
* Expand tabs;

* Free software: MIT license


Usage
-----

This repository provides a tool ``fix-format`` (or ``ff`` for short) which can be used to format files automatically
or check if some files are already formatted (usually in a ``pre-commit`` hook).

1. To manually format files and/or directories::

    fix-format <file1> <dir1> ...


2. Format modified files in Git::

    fix-format --commit

   Or more succinctly::

    ff -c

3. Use as Git hook:

.. code-block:: bash

    #!/bin/sh
    # fix-format pre-commit check
    # installed automatically by the "hooks" task, changes will be lost!

    if ! which fix-format >/dev/null 2>&1
    then
        echo "fix-format not found, change to conda root and install with:"
        echo "  conda install esss_fix_format"
        exit 1
    fi

    git diff-index --name-only --cached HEAD | fix-format --check --stdin
    returncode=$?
    if [ "$returncode" != "0" ]
    then
        echo ""
        echo "fix-format check failed (status=$returncode)! To fix, execute:"
        echo "  ff -c"
        exit 1
    fi


Migrating a project to use fix-format
-------------------------------------

Follow this steps to re format an entire project and start using the pre-commit hook:

1. Search for all usages of ``coilib50.LoadCppModule`` function, and for each file that
   uses it add ``isort:skipfile`` to the docstring:

    .. code-block:: python

        """
        module docstring contents..*:

        isort:skip_file
        """

   Commit using ``-n`` to skip the current hook.

2. If there are any sensitive imports in your code which you wouldn't like to ``ff`` to touch, use
   a comment to prevent ``isort`` from touching it:

    .. code-block:: python

        ConfigurePyroSettings()  # must be called before importing Pyro4
        import Pyro4  # isort:skip

3. Execute:

    .. code-block:: sh

        $ ff /path/to/repo/root

   After it completes, make sure there are no problems with the files:

    .. code-block:: sh

        $ ff /path/to/repo/root --check

   .. note::
        if the check fails, try running it again; there's a rare
        `bug in isort <https://github.com/timothycrosley/isort/issues/460>`_ that might
        require to run ``ff /path/to/repo/root`` twice.

   Commit:

    .. code-block:: sh

        $ git commit -anm "Apply fix-format on all files" --author="Dev <dev@esss.com.br>"


4. Execute ``codegen`` and check if no files were modified:

    .. code-block:: sh

        $ ff /path/to/repo/root --check

5. Push and run your branch on CI.

6. If all goes well, finally make ``codegen`` install the hook automatically in your ``tasks.py``:

    .. code-block:: python

        @ctask
        def _codegen(ctx, cache='none', flags=''):
            ns.tasks['constants'](ctx)
            ns.tasks['hooks'](ctx)


7. Profit!


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage

