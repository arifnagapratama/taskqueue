"""Generate deployment secrets once; run from the repository root."""
import ipaddress
import os
from pathlib import Path
import secrets
import re
import subprocess
import tempfile


def openssl(*arguments):
    return subprocess.run(['openssl', *map(str, arguments)], check=True,
                          capture_output=True, text=True).stdout


def certificate_pair(cert, key):
    if cert.exists() != key.exists():
        raise SystemExit(f'Incomplete certificate pair: {cert}, {key}; restore the missing file.')
    if cert.exists():
        text = openssl('x509', '-in', cert, '-noout', '-text')
        extensions = re.findall(r'^\s+X509v3 ([^:\n]+):', text, flags=re.MULTILINE)
        if len(extensions) != len(set(extensions)):
            raise SystemExit(f'Duplicate X509v3 extensions in {cert}. Stop Compose, archive '
                             'ca.crt/ca.key and server.crt/server.key, remove those certificate '
                             'pairs, rerun initialization, and trust the new ca.crt on clients. '
                             'Keep the token file.')
        if openssl('x509', '-in', cert, '-pubkey', '-noout') != openssl('pkey', '-in', key, '-pubout'):
            raise SystemExit(f'Certificate and private key do not match: {cert}, {key}')
    return cert.exists()


def certificates(directory, address):
    cert, key = directory / 'server.crt', directory / 'server.key'
    ca, ca_key = directory / 'ca.crt', directory / 'ca.key'
    server_exists = certificate_pair(cert, key)
    if server_exists and 'CA:FALSE' not in openssl('x509', '-in', cert, '-noout', '-ext', 'basicConstraints'):
        raise SystemExit('Legacy HTTPS certificate is not CA:FALSE. Stop Compose, archive '
                         'server.crt/server.key, remove that pair, rerun initialization, '
                         'then trust ca.crt on clients and restart Compose. Keep the token file.')
    ca_exists = certificate_pair(ca, ca_key)
    if server_exists and not ca_exists:
        raise SystemExit('Existing server certificate has no local CA pair; restore ca.crt/ca.key '
                         'or archive the server pair and rerun initialization.')
    if not ca_exists:
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / 'ca.cnf'
            config.write_text(
                '[req]\ndistinguished_name=dn\n[dn]\n'
                '[ca_extensions]\n'
                'basicConstraints=critical,CA:TRUE,pathlen:0\n'
                'keyUsage=critical,keyCertSign,cRLSign\n'
                'subjectKeyIdentifier=hash\n')
            openssl('req', '-x509', '-newkey', 'rsa:3072', '-sha256', '-nodes',
                    '-days', '3650', '-subj', '/CN=Task Queue Local CA',
                    '-config', config, '-extensions', 'ca_extensions',
                    '-keyout', ca_key, '-out', ca)
    if not server_exists:
        with tempfile.TemporaryDirectory() as temporary:
            csr = Path(temporary) / 'server.csr'
            config = Path(temporary) / 'req.cnf'
            config.write_text('[req]\ndistinguished_name=dn\n[dn]\n')
            extensions = Path(temporary) / 'server.ext'
            extensions.write_text(
                'basicConstraints=critical,CA:FALSE\n'
                'keyUsage=critical,digitalSignature,keyEncipherment\n'
                'extendedKeyUsage=serverAuth\n'
                f'subjectAltName=IP:{address}\n'
                'subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
            openssl('req', '-new', '-newkey', 'rsa:3072', '-nodes', '-sha256',
                    '-config', config, '-subj', '/CN=Task Queue', '-keyout', key, '-out', csr)
            openssl('x509', '-req', '-in', csr, '-CA', ca, '-CAkey', ca_key,
                    '-set_serial', str(secrets.randbits(159) or 1), '-days', '365',
                    '-sha256', '-extfile', extensions, '-out', cert)
    for path in (key, ca_key):
        path.chmod(0o600)
    for path in (cert, ca):
        path.chmod(0o644)
    openssl('verify', '-x509_strict', '-purpose', 'sslserver', '-verify_ip', address,
            '-CAfile', ca, cert)


def main():
    os.umask(0o077)
    config = Path('.env')
    if not config.is_file():
        raise SystemExit('Copy .env.example to .env and set TASKQUEUE_IP first.')
    values = {}
    for line in config.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('\"\'')
    address = str(ipaddress.ip_address(values.get('TASKQUEUE_IP', '')))
    directory = Path('deploy/private')
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o755)
    token = directory / 'token'
    if not token.exists():
        with token.open('x') as output:
            output.write(secrets.token_urlsafe(48) + '\n')
    # Container UID 10001 must read the token; private directory is host-owned.
    os.chown(token, 10001, -1)
    os.chmod(token, 0o400)
    try:
        certificates(directory, address)
    except subprocess.CalledProcessError as error:
        details = '\n'.join(part.strip() for part in (error.stdout, error.stderr) if part and part.strip())
        raise SystemExit(
            f'OpenSSL failed (exit {error.returncode}).\n{details}\n'
            'Initialization did not complete. Inspect the OpenSSL diagnostic above; '
            'keep existing certificate files and token until the cause is identified.'
        ) from None
    print('Deployment files ready in deploy/private. Trust ca.crt on clients; keep private keys on the server.')


if __name__ == '__main__':
    main()
