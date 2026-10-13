"""Private native component metadata and file inspection without application imports."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

COMPONENT = 'components/opermem/linux-x86_64-gnu'
EXECUTABLES = ('opermem-operation-host', 'opermem-child')


def component_manifest(files, evidence):
    return {'version': 1, 'platform': 'linux-x86_64-gnu', 'glibc_minimum': '2.39',
            'system_libraries': ['libc.so.6', 'libgcc_s.so.1', 'libm.so.6', 'ld-linux-x86-64.so.2'],
            'sqlite': 'bundled', 'protocol': 'accepted-operation-host/child',
            'privacy': 'PRIVATE OWNER DELIVERY', 'source_authority': 'independent Opermem repository; no declared redistribution license',
            'evidence': evidence, 'files': {name: hashlib.sha256(files[name]).hexdigest() for name in EXECUTABLES}}


def validate_component(files, manifest):
    if (not isinstance(manifest, dict) or manifest.get('version') != 1
            or manifest.get('platform') != 'linux-x86_64-gnu' or manifest.get('glibc_minimum') != '2.39'
            or manifest.get('privacy') != 'PRIVATE OWNER DELIVERY'
            or not isinstance(manifest.get('evidence'), dict) or not manifest['evidence']
            or set(manifest.get('files', {})) != set(EXECUTABLES)):
        raise ValueError('Unsupported Opermem component manifest')
    for name in EXECUTABLES:
        data = files[name]
        if (hashlib.sha256(data).hexdigest() != manifest['files'][name]
                or data[:4] != b'\x7fELF' or data[4:6] != b'\x02\x01' or data[18:20] != b'\x3e\x00'):
            raise ValueError('Opermem component bytes/hash/architecture mismatch: ' + name)


def check_platform():
    libc, version = platform.libc_ver()
    if (sys.platform != 'linux' or platform.machine() not in ('x86_64', 'amd64')
            or libc != 'glibc' or tuple(map(int, version.split('.')[:2])) < (2, 39)):
        raise ValueError('Packaged Opermem requires Linux x86_64 and glibc >=2.39')


def host_configuration(explicit=None):
    """Inspect configuration/files only; no native startup on browse."""
    selected = explicit or os.environ.get('NOETIC_OPERMEM_HOST')
    if not selected:
        return {'configured': False, 'available': False, 'host': None,
                'reason': 'No installation Opermem host configured; explicitly select a backing after configuration.'}
    try:
        supplied = Path(selected).expanduser()
        if not supplied.is_absolute():
            raise ValueError('Installation Opermem host must be absolute')
        host = supplied.resolve(strict=True)
        child = host.parent / 'opermem-child'
        if host.name != EXECUTABLES[0] or not host.is_file() or not os.access(host, os.X_OK):
            raise ValueError('Opermem host is missing or not executable')
        if child.is_symlink() or not child.is_file() or not os.access(child, os.X_OK):
            raise ValueError('Opermem requires its executable regular sibling opermem-child')
        manifest_path = host.parent / 'component.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            validate_component({n: (host.parent / n).read_bytes() for n in EXECUTABLES}, manifest)
            check_platform()
        return {'configured': True, 'available': True, 'host': str(host), 'child': str(child),
                'native_started': False, 'reason': 'Files configured; native state and provider readiness remain unobserved.'}
    except (OSError, ValueError, KeyError, IndexError) as exc:
        return {'configured': True, 'available': False, 'host': str(selected), 'native_started': False, 'reason': str(exc)}


