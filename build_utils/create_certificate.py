import os
import subprocess
import sys
import yaml

def run():
    paths = yaml.load(open('create_certificate.yaml'), Loader=yaml.FullLoader)

    try:
        if not os.path.isfile(paths['openssl_path']):
            raise ValueError("The path provided for the OpenSSL executable is invalid")
    except KeyError:
        raise RuntimeError("Please define a 'openssl_path' variable in the \
                            create_certificate.yaml configuration file. This can found within a \
                            Miniconda/Anaconda installation, under /Library/bin/openssl.exe")
    try:
        if not os.path.isfile(paths['openssl_config']):
            raise ValueError("The path provided for the OpenSSL configuration is invalid")
    except KeyError:
        raise RuntimeError("Please define a 'openssl_config' variable in the \
                            create_certificate.yaml configuration file. This can found within a \
                            Miniconda/Anaconda installation, under /Library/openssl.cnf")
    try:
        if not os.path.isfile(paths['signtool_path']):
            raise ValueError("The path provided for the SignTool executable is invalid")
    except KeyError:
        raise RuntimeError("Please define a 'signtool_path' variable in the \
                            create_certificate.yaml configuration file. This can found in \
                            C:/Program Files/Microsoft SDKs/Windows/bin/signtool.exe")

    if not os.path.isfile('xgis_ssl.key') or not os.path.isfile('xgis_ssl.crt'):

        print("> Creating Certificate/Key (.pem/.key) pair")
        certificate_call_args = [
            paths['openssl_path'],
            'req',
            '-config', paths['openssl_config'],
            '-x509',
            '-newkey', 'rsa:4096',
            '-sha256',
            '-keyout', 'xgis_ssl.key',
            '-out', 'xgis_ssl.crt',
            '-days', '600',
        ]

        subprocess.call(certificate_call_args)
    
    if not os.path.isfile('xgis_ssl.pfx'):

        print("> Creating Personal Exchange Format (.pfx) file")
        certificate_call_args = [
            paths['openssl_path'],
            'pkcs12',
            '-export', '-noiter',
            '-in', 'xgis_ssl.crt',
            '-inkey', 'xgis_ssl.key',
            '-out', 'xgis_ssl.pfx',
        ]

        subprocess.call(certificate_call_args)




if __name__ == "__main__":
    run()