import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('init_deploy', Path(__file__).with_name('init-deploy.py'))
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


def test_server_chain_and_preservation(tmp_path, monkeypatch):
    system_config = tmp_path / 'system.cnf'
    system_config.write_text(
        '[req]\ndistinguished_name=dn\nx509_extensions=defaults\n[dn]\n'
        '[defaults]\nbasicConstraints=critical,CA:TRUE\nsubjectKeyIdentifier=hash\n')
    monkeypatch.setenv('OPENSSL_CONF', str(system_config))
    deployment.certificates(tmp_path, '192.168.10.5')
    server = deployment.openssl('x509', '-in', tmp_path / 'server.crt', '-noout', '-text')
    assert 'CA:FALSE' in server
    assert 'TLS Web Server Authentication' in server
    assert 'IP Address:192.168.10.5' in server
    ca = deployment.openssl('x509', '-in', tmp_path / 'ca.crt', '-noout', '-text')
    assert 'CA:TRUE' in ca
    assert ca.count('X509v3 Basic Constraints:') == 1
    assert ca.count('X509v3 Subject Key Identifier:') == 1
    assert server.count('X509v3 Basic Constraints:') == 1
    assert server.count('X509v3 Subject Key Identifier:') == 1
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    deployment.certificates(tmp_path, '192.168.10.5')
    assert original == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(subprocess.CalledProcessError):
        deployment.certificates(tmp_path, '192.168.10.6')


def test_legacy_ca_end_entity_rejected(tmp_path):
    deployment.openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                       '-subj', '/CN=Legacy', '-addext', 'basicConstraints=CA:TRUE',
                       '-keyout', tmp_path / 'server.key', '-out', tmp_path / 'server.crt')
    previous = (tmp_path / 'server.crt').read_bytes()
    with pytest.raises(SystemExit, match='Legacy HTTPS certificate'):
        deployment.certificates(tmp_path, '192.168.10.5')
    assert (tmp_path / 'server.crt').read_bytes() == previous
    assert not (tmp_path / 'ca.crt').exists()


def test_main_reports_openssl_diagnostics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.env').write_text('TASKQUEUE_IP=192.168.10.5\n')
    monkeypatch.setattr(deployment.os, 'chown', lambda *args: None)

    def failed_verification(*args):
        raise subprocess.CalledProcessError(
            2, ['openssl', 'verify'], output='verification failed\n',
            stderr='error 64 at 0 depth lookup: IP address mismatch\n')

    monkeypatch.setattr(deployment, 'certificates', failed_verification)
    previous_umask = os.umask(0o077)
    try:
        with pytest.raises(SystemExit) as error:
            deployment.main()
    finally:
        os.umask(previous_umask)
    message = str(error.value)
    assert 'OpenSSL failed (exit 2)' in message
    assert 'verification failed' in message
    assert 'IP address mismatch' in message
    assert 'keep existing certificate files and token' in message


def test_duplicate_extensions_rejected_without_modification(tmp_path, monkeypatch):
    cert, key = tmp_path / 'ca.crt', tmp_path / 'ca.key'
    cert.write_text('existing certificate')
    key.write_text('existing key')
    monkeypatch.setattr(deployment, 'openssl', lambda *args:
                        '            X509v3 Basic Constraints: critical\n'
                        '                CA:TRUE\n'
                        '            X509v3 Basic Constraints: critical\n'
                        '                CA:TRUE, pathlen:0\n')
    with pytest.raises(SystemExit, match='Duplicate X509v3 extensions') as error:
        deployment.certificate_pair(cert, key)
    assert 'Keep the token file' in str(error.value)
    assert cert.read_text() == 'existing certificate'
    assert key.read_text() == 'existing key'
