from base64 import urlsafe_b64encode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

key = ec.generate_private_key(ec.SECP256R1())
private_pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode('utf-8')
public_raw = key.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
public_key = urlsafe_b64encode(public_raw).rstrip(b'=').decode('ascii')
print('VAPID_PUBLIC_KEY=')
print(public_key)
print('\nVAPID_PRIVATE_KEY=')
print(private_pem)
print('\nVAPID_CLAIMS_EMAIL=mailto:YOUR-EMAIL@example.com')
