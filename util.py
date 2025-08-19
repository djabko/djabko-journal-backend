# Access control is done via RSA asymmetric cryptography:
#   public key is used for read access
#   private key is used for write access
#   both are generated during notebook creation

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

class Notebook:

    def create(notebook_id):
        pass

    def log(notebook_id, priv):
        pass

    def delete(notebook_id, priv):
        pass

    def read(notebook_id):
        pass
