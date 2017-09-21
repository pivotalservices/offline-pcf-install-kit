#!/bin/bash

set -o errexit

if [ -e certs ]; then
    rm -rf certs
fi

mkdir certs
cd certs

cat > openssl.cnf <<EOL
[ ca ]
default_ca      = CA_default            # The default ca section
[ CA_default ]
dir             = ./demoCA              # Where everything is kept
certs           = $dir/certs            # Where the issued certs are kept
crl_dir         = $dir/crl              # Where the issued crl are kept
database        = $dir/index.txt        # database index file.
new_certs_dir   = $dir/newcerts         # default place for new certs.
certificate     = $dir/cacert.pem       # The CA certificate
serial          = $dir/serial           # The current serial number
crlnumber       = $dir/crlnumber        # the current crl number
crl             = $dir/crl.pem          # The current CRL
private_key     = $dir/private/cakey.pem# The private key
RANDFILE        = $dir/private/.rand    # private random number file
x509_extensions = usr_cert              # The extentions to add to the cert
name_opt        = ca_default            # Subject Name options
cert_opt        = ca_default            # Certificate field options
[ req ]
distinguished_name      = req_distinguished_name
x509_extensions = v3_ca # The extentions to add to the self signed cert
[ req_distinguished_name ]
commonName                      = Common Name (e.g. server FQDN or YOUR name)
[ usr_cert ]
basicConstraints=CA:FALSE
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment, dataEncipherment, keyAgreement
extendedKeyUsage=serverAuth, clientAuth
[ v3_ca ]
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid:always,issuer:always
basicConstraints = critical,CA:true,pathlen:0
keyUsage = cRLSign, keyCertSign

EOL

openssl genrsa 3072 > pcf-ipsec-ca-key.pem
openssl req -x509 -new -nodes -days 1095 -sha256 -config openssl.cnf -key pcf-ipsec-ca-key.pem -subj /CN=PCF\ IPsec\ AddOn\ CA -out pcf-ipsec-ca-cert.pem
openssl req -newkey rsa:2048 -days 365 -nodes -sha256 -subj /CN=PCF\ IPsec\ peer -keyout pcf-ipsec-peer-key.pem -out pcf-ipsec-peer-req.pem
openssl x509 -req -in pcf-ipsec-peer-req.pem -days 365 -extfile openssl.cnf -extensions v3_req -CA pcf-ipsec-ca-cert.pem -CAkey pcf-ipsec-ca-key.pem -set_serial 01 -out pcf-ipsec-peer-cert.pem
openssl x509 -inform pem -in pcf-ipsec-peer-cert.pem -text
openssl x509 -inform pem -in pcf-ipsec-ca-cert.pem  -text

rm -f openssl.cnf
rm -f pcf-ipsec-peer-req.pem

echo " "
echo "New IPsec certificates created in ./certs subdirectory:"
echo " "

ls -la

cd ..
