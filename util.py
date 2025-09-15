# Access control is done via RSA asymmetric cryptography:
#   public key is used for read access
#   private key is used for write access
#   both are generated during notebook creation

class Notebook:

    def create(notebook_id):
        pass

    def log(notebook_id, priv):
        pass

    def delete(notebook_id, priv):
        pass

    def read(notebook_id):
        pass


class JournalConstant:
    trans_dict = {}
    r_trans_dict = {}

    def __init__(self, raw, label):
        self.raw = raw
        self.label = label

        JournalConstant.trans_dict[raw] = label
        JournalConstant.r_trans_dict[label] = raw

    def __str__(self):
        return f'({self.raw}: {self.label})';


class Constants:
    NOTEBOOK = JournalConstant('notebook', 'Notebook')
    MESSAGE = JournalConstant('message', 'Message')
    DATETIME = JournalConstant('datetime', 'Datetime')
    AUTHOR = JournalConstant('author', 'Author')
    TAG1 = JournalConstant('tag1', 'Tag 1')
    TAG2 = JournalConstant('tag2', 'Tag 2')
    TAG3 = JournalConstant('tag3', 'Tag 3')
    TAG4 = JournalConstant('tag4', 'Tag 4')

    trans_dict = JournalConstant.trans_dict
    r_trans_dict = JournalConstant.r_trans_dict
