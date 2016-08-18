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


Credits
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage

