import pytest
from packaging.requirements import Requirement
from packaging.version import Version, parse
from pynixify.exceptions import PackageNotFound
from pynixify.nixpkgs_sources import (
    NixpkgsData,
    NixPackage,
)


ZSTD_DATA = {
    'zstd': [{
        'attr': 'zstd',
        'pypiName': 'zstd',
        'src': "mirror://pypi/z/zstd/zstd-1.4.4.0.tar.gz",
        'version': "1.4.4.0",
    }]
}


PYTESTRUNNER_DATA = {
    "pyTEST-runner": [{
        "attr": "pytestrunner",
        "pypiName": "pytest-runner",
        "src": "mirror://pypi/p/pytest-runner/pytest-runner-5.1.tar.gz",
        "version": "5.1"
    }]
}


MULTIVERSION_DATA = {
    "a": [
        {"attr": "a1", "pypiName": "a", "version": "1.0.1"},
        {"attr": "a3", "pypiName": "a", "version": "3.0.0"},
        {"attr": "a2", "pypiName": "a", "version": "2.3"},
    ]
}


CANONICALIZE_COLLISION_DATA = {
    "a-b": [{
        "attr": "xxx",
        "pypiName": "a-b",
        "version": "1",
        "src": "mirror://pypi/a/a-b/a-b-1.tar.gz",
    }],
    "A_B": [{
        "attr": "yyy",
        "pypiName": "a-b",
        "version": "2",
        "src": "mirror://pypi/a/a-b/a-b-1.tar.gz",
    }],
}


def test_parse_json():
    repo = NixpkgsData(ZSTD_DATA)
    repo.from_pypi_name('zstd')


def test_invalid_pypi_name():
    repo = NixpkgsData({})
    with pytest.raises(PackageNotFound):
        repo.from_pypi_name('zstd')
    with pytest.raises(PackageNotFound):
        repo.from_requirement(Requirement('zstd'))


def test_not_case_sensitive():
    repo = NixpkgsData(ZSTD_DATA)
    repo.from_pypi_name('ZSTD')


def test_canonicalize():
    repo = NixpkgsData(PYTESTRUNNER_DATA)
    repo.from_pypi_name('PYTEST_RUNNER')


def test_canonicalize_collision():
    repo = NixpkgsData(CANONICALIZE_COLLISION_DATA)
    repo.from_requirement(Requirement('a_B==1'))
    repo.from_requirement(Requirement('A-b==2'))


def test_from_pypi_name_response():
    repo = NixpkgsData(PYTESTRUNNER_DATA)
    drvs = repo.from_pypi_name('pytest-runner')
    assert isinstance(drvs, list)
    assert isinstance(drvs[0], NixPackage)
    assert drvs[0].attr == 'pytestrunner'
    assert drvs[0].version == parse('5.1')


def test_from_requirement():
    repo = NixpkgsData(MULTIVERSION_DATA)
    drvs = repo.from_requirement(Requirement('a>=3'))
    assert len(drvs) == 1
    assert drvs[0].attr == 'a3'
    assert drvs[0].version == parse('3.0.0')
