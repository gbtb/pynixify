# pynixify - Nix expression generator for Python packages
# Copyright (C) 2020 Matías Lang

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import json
import pytest
from pathlib import Path
from pynixify.base import Package
from packaging.requirements import Requirement
from pynixify.package_requirements import PackageRequirements
from pynixify.nixpkgs_sources import (
    NixpkgsData,
    NixPackage,
)
from pynixify.pypi_api import (
    PyPIData,
    PyPIPackage,
)
from pynixify.version_chooser import (
    VersionChooser,
    ChosenPackageRequirements,
)
from pynixify.exceptions import (
    NoMatchingVersionFound,
    PackageNotFound,
)
from .test_pypi_api import DummyCache, SAMPLEPROJECT_DATA


ZSTD_DATA = {
    'zstd': [{
        'attr': 'zstd',
        'pypiName': 'zstd',
        'src': "mirror://pypi/z/zstd/zstd-1.4.4.0.tar.gz",
        'version': "1.4.4.0",
    }]
}

NIXPKGS_SAMPLEPROJECT = {
    'sampleproject': [{
        'attr': 'anything',
        'pypiName': 'sampleproject',
        'src': "mirror://pypi/s/sampleproject/sampleproject-1.0.tar.gz",
        'version': "1.0",
    }]
}

MULTIVERSION_DATA = {
    "a": [
        {"attr": "a1", "pypiName": "a", "version": "1.0.1"},
        {"attr": "a24", "pypiName": "a", "version": "2.4"},
        {"attr": "a3", "pypiName": "a", "version": "3.0.0"},
        {"attr": "a2", "pypiName": "a", "version": "2.3"},
    ]
}

dummy_pypi = PyPIData(DummyCache())


with (Path(__file__).parent / "nixpkgs_packages.json").open() as fp:
    NIXPKGS_JSON = json.load(fp)


def dummy_package_requirements(hardcoded_reqs={}):
    async def f(package: Package) -> PackageRequirements:
        nonlocal hardcoded_reqs
        (b, t, r) = hardcoded_reqs.get(package.attr, ([], [], []))
        reqs = PackageRequirements(b, t, r)
        return reqs
    return f


def assert_version(c: VersionChooser, package_name: str, version: str):
    p = c.package_for(package_name)
    assert p is not None
    assert str(p.version) == version


@pytest.mark.asyncio
async def test_nixpkgs_package():
    nixpkgs = NixpkgsData(ZSTD_DATA)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
    await c.require(Requirement('zstd==1.4.4.0'))


@pytest.mark.asyncio
async def test_package_for_canonicalizes():
    nixpkgs = NixpkgsData(ZSTD_DATA)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
    await c.require(Requirement('ZSTD==1.4.4.0'))
    assert c.package_for('zstd') is c.package_for('ZSTD')


#@pytest.mark.asyncio
#async def test_invalid_package():
#    nixpkgs = NixpkgsData({})
#    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
#    with pytest.raises(PackageNotFound):
#        await c.require(Requirement('zstd==1.4.4.0'))


#@pytest.mark.asyncio
#async def test_no_matching_version():
#    nixpkgs = NixpkgsData(ZSTD_DATA)
#    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
#    with pytest.raises(NoMatchingVersionFound):
#        await c.require(Requirement('zstd>1.4.4.0'))


#@pytest.mark.asyncio
#async def test_no_matching_version_on_second_require():
#    nixpkgs = NixpkgsData(ZSTD_DATA)
#    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
#    await c.require(Requirement('zstd==1.4.4.0'))
#    with pytest.raises(NoMatchingVersionFound):
#        await c.require(Requirement('zstd<1.4.4.0'))

@pytest.mark.asyncio
async def test_no_matching_version_with_previous_requirements():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
    await c.require(Requirement('django==2.1.14'))
    with pytest.raises(NoMatchingVersionFound):
        await c.require(Requirement('django>=2.2'))


@pytest.mark.asyncio
async def test_multi_nixpkgs_versions():
    nixpkgs = NixpkgsData(MULTIVERSION_DATA)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
    await c.require(Requirement('a>=2.0.0'))
    assert_version(c, 'a', '3.0.0')


@pytest.mark.asyncio
async def test_uses_runtime_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements({
        "django_2_2": ([], [], [Requirement('pytz')]),
    }))
    await c.require(Requirement('django>=2.2'))
    assert c.package_for('django')
    assert c.package_for('pytz')
    assert_version(c, 'pytz', '2019.3')


@pytest.mark.asyncio
async def test_test_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(
        nixpkgs, dummy_pypi,
        should_load_tests=lambda _: False,
        req_evaluate=dummy_package_requirements({
            "django_2_2": ([], [Requirement('pytest')], []),
        }
    ))
    await c.require(Requirement('django>=2.2'))
    assert c.package_for('django')
    assert c.package_for('pytest') is None


@pytest.mark.asyncio
async def test_use_build_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements({
        "pytz": ([Requirement('setuptools_scm')], [], []),
    }))
    await c.require(Requirement('pytz'))
    assert c.package_for('pytz')
    assert c.package_for('setuptools_scm')

@pytest.mark.asyncio
async def test_nixpkgs_transitive():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements({
        'flask': ([], [], [Requirement("itsdangerous")]),
        'itsdangerous': ([], [], [Requirement('Werkzeug')]),
    }))
    await c.require(Requirement('flask'))
    assert c.package_for('flask')
    assert c.package_for('itsdangerous')
    assert c.package_for('Werkzeug')


@pytest.mark.asyncio
async def test_circular_dependencies():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements({
        'flask': ([], [], [Requirement("itsdangerous")]),
        'itsdangerous': ([], [Requirement('flask')], []),
    }))
    await c.require(Requirement('flask'))
    assert c.package_for('flask')
    assert c.package_for('itsdangerous')

@pytest.mark.asyncio
@pytest.mark.parametrize('load_tests', [True, False])
async def test_pypi_package(load_tests):
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    c = VersionChooser(
        nixpkgs, pypi,
        req_evaluate=dummy_package_requirements({
            'sampleproject': ([], [Requirement('pytest')], []),
        }),
        should_load_tests=lambda _: load_tests)
    await c.require(Requirement('sampleproject'))
    assert_version(c, 'sampleproject', '1.3.1')
    if load_tests:
        assert c.package_for('pytest') is not None
    else:
        assert c.package_for('pytest') is None

@pytest.mark.asyncio
async def test_prefer_nixpkgs_older_version():
    nixpkgs = NixpkgsData(NIXPKGS_SAMPLEPROJECT)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    c = VersionChooser(nixpkgs, pypi, dummy_package_requirements())
    await c.require(Requirement('sampleproject'))
    assert_version(c, 'sampleproject', '1.0')
    with pytest.raises(NoMatchingVersionFound):
        await c.require(Requirement('sampleproject>1.0'))

@pytest.mark.asyncio
async def test_pypi_dependency_uses_nixpkgs_dependency():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    c = VersionChooser(nixpkgs, pypi, dummy_package_requirements({
        "sampleproject": ([], [], [Requirement('flask')]),
    }))
    await c.require(Requirement('sampleproject'))
    assert c.package_for('sampleproject')
    assert c.package_for('flask')

@pytest.mark.asyncio
async def test_nixpkgs_dependency_with_unmatched_requirements():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache())
    c = VersionChooser(nixpkgs, pypi, dummy_package_requirements({
        "botocore": ([], [], [Requirement('docutils<0.15')]),
    }))
    await c.require(Requirement('botocore'))
    botocore = c.package_for('botocore')
    assert botocore is not None
    assert isinstance(botocore, NixPackage)
    docutils = c.package_for('docutils')
    assert docutils is None

@pytest.mark.asyncio
async def test_conflicting_versions():
    data = NIXPKGS_JSON.copy()
    nixpkgs = NixpkgsData(data)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    c = VersionChooser(nixpkgs, pypi, dummy_package_requirements({
        "flask": ([], [], [Requirement('sampleproject==1.0')]),
        "click": ([], [], [Requirement('sampleproject>1.0')]),
    }))
    await c.require(Requirement('click'))
    assert c.package_for('click')
    with pytest.raises(NoMatchingVersionFound):
        await c.require(Requirement('flask'))

@pytest.mark.asyncio
async def test_python_version_marker():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    c = VersionChooser(nixpkgs, dummy_pypi, dummy_package_requirements())
    await c.require(Requirement("flask; python_version<'3'"))
    assert c.package_for('flask') is None


@pytest.mark.asyncio
async def test_all_pypi_packages():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    c = VersionChooser(nixpkgs, pypi, dummy_package_requirements({
        "sampleproject": ([], [], [Requirement('flask')]),
    }))
    await c.require(Requirement('sampleproject'))
    sampleproject = c.package_for('sampleproject')
    assert c.all_pypi_packages() == [sampleproject]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'load_tests', [True, False],
    ids=["Load test requirements", "Don't load test requirements"]
)
@pytest.mark.parametrize(
    'require_pytest', [True, False],
    ids=["Require pytest before sample project", "Don't require pytest directly"]
)
async def test_chosen_package_requirements(load_tests, require_pytest):
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    reqs_f = dummy_package_requirements({
        "sampleproject": ([], [Requirement('pytest')], [Requirement('flask')]),
    })
    c = VersionChooser(nixpkgs, pypi, reqs_f,
                       should_load_tests=lambda _: load_tests)
    if require_pytest:
        await c.require(Requirement('pytest'))
    await c.require(Requirement('sampleproject'))
    sampleproject = c.package_for('sampleproject')
    reqs: PackageRequirements = await reqs_f(sampleproject)

    chosen: ChosenPackageRequirements
    chosen = ChosenPackageRequirements.from_package_requirements(
        reqs, c, load_tests=load_tests)

    assert len(chosen.runtime_requirements) == 1
    assert len(chosen.test_requirements) == int(load_tests)
    assert chosen.runtime_requirements[0] is c.package_for('flask')


@pytest.mark.asyncio
async def test_always_ignores_nixpkgs_test_requirements():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    reqs_f = dummy_package_requirements({
        "sampleproject": ([], [Requirement('pytest')], [Requirement('flask')]),
    })
    def should_load_tests(package_name):
        # Flask should be a NixPackage. We don't care about its test requirements
        assert package_name != 'flask'
        return True
    c = VersionChooser(nixpkgs, pypi, reqs_f,
                       should_load_tests=should_load_tests)
    await c.require(Requirement('sampleproject'))
    assert c.package_for('sampleproject')
    assert c.package_for('pytest')


@pytest.mark.asyncio
async def test_chosen_package_requirements_marker():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    req = Requirement("notexistent; python_version<'3'")
    reqs_f = dummy_package_requirements({
        "sampleproject": ([req], [], [req]),
    })
    c = VersionChooser(nixpkgs, pypi, reqs_f)
    await c.require(Requirement('sampleproject'))
    sampleproject = c.package_for('sampleproject')
    reqs: PackageRequirements = await reqs_f(sampleproject)

    chosen: ChosenPackageRequirements
    chosen = ChosenPackageRequirements.from_package_requirements(
        reqs, c, load_tests=True)

    assert len(chosen.runtime_requirements) == 0


#@pytest.mark.asyncio
#async def test_chosen_package_requirements_fails():
#    nixpkgs = NixpkgsData(NIXPKGS_JSON)
#    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
#    c = VersionChooser(nixpkgs, pypi, dummy_package_requirements())
#    reqs = PackageRequirements(
#        build_requirements=[],
#        test_requirements=[],
#        runtime_requirements=[Requirement('invalid')]
#    )
#    with pytest.raises(PackageNotFound):
#        ChosenPackageRequirements.from_package_requirements(
#            reqs, c, load_tests=True)


@pytest.mark.asyncio
async def test_require_local_package():
    nixpkgs = NixpkgsData(NIXPKGS_JSON)
    pypi = PyPIData(DummyCache(sampleproject=SAMPLEPROJECT_DATA))
    reqs_f = dummy_package_requirements({
        "sampleproject": ([], [], [Requirement('flask')]),
    })
    c = VersionChooser(nixpkgs, pypi, reqs_f)
    await c.require_local('sampleproject', Path('/src'))
    sampleproject = c.package_for('sampleproject')
    assert sampleproject is not None
    assert isinstance(sampleproject, PyPIPackage)
    assert c.package_for('flask')
    src = await sampleproject.source()
    assert src == Path('/src')
