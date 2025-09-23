import secrets, string

from argon2 import PasswordHasher
from boto3.dynamodb.conditions import Key


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

    PASSWORD = JournalConstant('password', 'Password')

    trans_dict = JournalConstant.trans_dict
    r_trans_dict = JournalConstant.r_trans_dict


class Authenticator:

    def hash(string):
        return PasswordHasher().hash(string)

    def auth(dynamo_table, notebook, password):
        hasher = PasswordHasher()
        kce = Key(Constants.NOTEBOOK.label).eq(notebook) \
                & Key(Constants.DATETIME.label).eq(Constants.PASSWORD.label)
        results = dynamo_table.query(KeyConditionExpression=kce)

        if 'Count' not in results         \
                or results['Count'] != 1  \
                or 'Items' not in results \
                or Constants.PASSWORD.label not in results['Items'][0]:

            # To protect against timing attacks, ensure request takes the same
            #   amount of time regardless of error.
            s = ''.join(secrets.choice(string.printable) for _ in range(10))
            hasher.hash(s)

            raise KeyError

        correct_hash = results['Items'][0][Constants.PASSWORD.label]
        hasher.verify(correct_hash, password)
        
