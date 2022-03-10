"""Nox sessions."""
import os
import shutil
import sys
from pathlib import Path
from textwrap import dedent
import nox

try:
    from nox_poetry import Session
    from nox_poetry import session

except ImportError:
    message = f"""\
    Nox failed to import the 'nox-poetry' package.

    Please install it using the following command:

    {sys.executable} -m pip install nox-poetry"""
    raise SystemExit(dedent(message)) from None

ON_TRAVIS_CI = os.environ.get("TRAVIS")
package = "tmi"
PYTHON_VERSIONS = ["3.10", "3.9"]
nox.needs_version = ">= 2022.1.7"
nox.options.sessions = (
    "pre-commit",
    "safety",
    "mypy",
    "tests",
    "typeguard",
    # "xdoctest",
    # "docs-build",
)


def activate_virtualenv_in_precommit_hooks(session: Session) -> None:
    """Activate virtualenv in hooks installed by pre-commit.

    This function patches git hooks installed by pre-commit to activate the
    session's virtual environment. This allows pre-commit to locate hooks in
    that environment when invoked from git.

    Args:
        session: The Session object.
    """
    assert session.bin is not None  # noqa: S101

    virtualenv = session.env.get("VIRTUAL_ENV")
    if virtualenv is None:
        return

    hookdir = Path(".git") / "hooks"
    if not hookdir.is_dir():
        return

    for hook in hookdir.iterdir():
        if hook.name.endswith(".sample") or not hook.is_file():
            continue

        text = hook.read_text()
        bindir = repr(session.bin)[1:-1]  # strip quotes
        if not (
            Path("A") == Path("a") and bindir.lower() in text.lower() or bindir in text
        ):
            continue

        lines = text.splitlines()
        if not (lines[0].startswith("#!") and "python" in lines[0].lower()):
            continue

        header = dedent(
            f"""\
            import os
            os.environ["VIRTUAL_ENV"] = {virtualenv!r}
            os.environ["PATH"] = os.pathsep.join((
                {session.bin!r},
                os.environ.get("PATH", ""),
            ))
            """
        )

        lines.insert(1, header)
        hook.write_text("\n".join(lines))


@session(name="pre-commit", python="3.10")
def precommit(session: Session) -> None:
    """Lint using pre-commit.

    Args:
        session (Session): A Nox Session.
    """
    args = session.posargs or ["run", "--all-files", "--show-diff-on-failure"]
    session.install(
        "black",
        "darglint",
        "flake8",
        "flake8-bandit",
        "flake8-bugbear",
        "flake8-black",
        "flake8-docstrings",
        "pep8-naming",
        "pre-commit",
        "pre-commit-hooks",
        "pyupgrade",
        "reorder-python-imports",
    )
    session.run("pre-commit", *args)
    if args and args[0] == "install":
        activate_virtualenv_in_precommit_hooks(session)


@session(python=PYTHON_VERSIONS)
def safety(session: Session) -> None:
    """Scan dependencies for insecure packages.

    Args:
        session (Session): A Nox Session.
    """
    requirements = session.poetry.export_requirements()
    session.install("safety")
    session.run("safety", "check", "--full-report", f"--file={requirements}")


@session(python=PYTHON_VERSIONS)
def mypy(session: Session) -> None:
    """Type-check using mypy.

    Args:
        session (Session): A Nox Session.
    """
    args = session.posargs or ["src", "tests"]
    session.install(".")
    session.install("mypy", "pytest")
    session.run("mypy", *args)
    if not session.posargs:
        session.run("mypy", f"--python-executable={sys.executable}", "noxfile.py")


@session(python=PYTHON_VERSIONS)
def tests(session: Session) -> None:
    """Run the test suite.

    Args:
        session (Session): A Nox Session.
    """
    session.install(".")
    session.install("coverage[toml]", "pytest", "pygments")
    try:
        session.run("coverage", "run", "--parallel", "-m", "pytest", *session.posargs)
    finally:
        if session.interactive:
            session.notify("coverage", posargs=[])


@session
def coverage(session: Session) -> None:
    """Produce the coverage report, and creates a report.

    Args:
        session (Session): A Nox Session.
    """
    report_args = session.posargs or ["report", "-m"]
    xml_args = session.posargs or ["xml", "-q"]
    coveralls_args = session.posargs or ["json"]

    session.install("coverage[toml]")

    if not session.posargs and any(Path().glob(".coverage.*")):
        session.run("coverage", "combine")

    session.run("coverage", *report_args)
    
    if ON_TRAVIS_CI:
        # If on Travis-CI create coverage json for coveralls
        session.run("coverage", *coveralls_args)
    else:
        # If on local machine, create coverage xml for extentions
        session.run("coverage", *xml_args)


@session(python=PYTHON_VERSIONS)
def typeguard(session: Session) -> None:
    """Runtime type checking using Typeguard.

    Args:
        session (Session): A Nox Session.
    """
    session.install(".")
    session.install("pytest", "typeguard", "pygments")
    session.run("pytest", f"--typeguard-packages={package}", *session.posargs)


# @session(python=python_versions)
# def xdoctest(session: Session) -> None:
#     """Run examples with xdoctest."""
#     if session.posargs:
#         args = [package, *session.posargs]
#     else:
#         args = [f"--modname={package}", "--command=all"]
#         if "FORCE_COLOR" in os.environ:
#             args.append("--colored=1")

#     session.install(".")
#     session.install("xdoctest[colors]")
#     session.run("python", "-m", "xdoctest", *args)


# @session(name="docs-build", python="3.10")
# def docs_build(session: Session) -> None:
#     """Build the documentation."""
#     args = session.posargs or ["docs", "docs/_build"]
#     if not session.posargs and "FORCE_COLOR" in os.environ:
#         args.insert(0, "--color")

#     session.install(".")
#     session.install("sphinx", "sphinx-click", "furo")

#     build_dir = Path("docs", "_build")
#     if build_dir.exists():
#         shutil.rmtree(build_dir)

#     session.run("sphinx-build", *args)


# @session(python="3.10")
# def docs(session: Session) -> None:
#     """Build and serve the documentation with live reloading on file changes."""
#     args = session.posargs or ["--open-browser", "docs", "docs/_build"]
#     session.install(".")
#     session.install("sphinx", "sphinx-autobuild", "sphinx-click", "furo")

#     build_dir = Path("docs", "_build")
#     if build_dir.exists():
#         shutil.rmtree(build_dir)

#     session.run("sphinx-autobuild", *args)
