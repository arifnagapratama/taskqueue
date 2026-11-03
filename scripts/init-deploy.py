"""Generate deployment secrets once; run from the repository root."""
import ipaddress
import os
from pathlib import Path
import secrets
import subprocess


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
    cert, key = directory / 'server.crt', directory / 'server.key'
    if cert.exists() != key.exists():
        raise SystemExit('Incomplete certificate pair; restore the missing file before continuing.')
    if not cert.exists():
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-sha256',
            '-nodes', '-days', '365', '-subj', '/CN=Task Queue',
            '-addext', f'subjectAltName=IP:{address}',
            '-keyout', str(key), '-out', str(cert),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(key, 0o600)
        os.chmod(cert, 0o644)
    result = subprocess.run(
        ['openssl', 'x509', '-in', str(cert), '-noout', '-checkip', address],
        check=True, capture_output=True, text=True,
    )
    if 'does match certificate' not in result.stdout:
        raise SystemExit('Existing certificate does not match TASKQUEUE_IP; renew the certificate pair.')
    print('Deployment files ready in deploy/private. Existing token and certificate preserved.')


if __name__ == '__main__':
    main()
