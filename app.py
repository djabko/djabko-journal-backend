#!python


import os, boto3, json, secrets, string, traceback

from datetime import datetime
from flask import Flask, request, redirect
from boto3.dynamodb.conditions import Key
from argon2.exceptions import VerifyMismatchError

from util import *


def get_priv(key):
    if key not in os.environ:
        raise KeyError(f'ERROR: missing environment variable {key}')

    return os.environ[key]

app = Flask(__name__)
dynamodb = boto3.resource(
            'dynamodb',
            region_name=get_priv('AWS_REGION'),
            endpoint_url=get_priv('ENDPOINT_URL')
        )
dynamo_table = dynamodb.Table(get_priv('TABLE_NAME'))


PREFIX = "journal"
VIEWS = [
        "create",
        "delete",
        "log",
        "read",
        ]

try:
    get_priv("APP_DEBUG_MODE")
    DEBUG_MODE = True
    print("Running in debug mode. App will print detailed logs. ")
except KeyError:
    DEBUG_MODE = False


def print_dbg(*args, **kwargs):
    if (DEBUG_MODE):
        print(*args, **kwargs)


def cat(prefix, suffix):
    return f'{prefix}-{suffix}'


@app.route("/journal/")
def index():
    return json.dumps({"views": [cat(PREFIX, x) for x in VIEWS]})


@app.post("/journal/create")
def journal_create():

    while True:
        data = request.json

        if Constants.PASSWORD.raw not in data:
            return '400 Missing Password'

        alphabet = string.ascii_letters + string.digits
        notebook = ''

        for i in range(3):
            s = ''.join(secrets.choice(alphabet) for _ in range(10))
            notebook += s + '-'

        notebook += ''.join(secrets.choice(alphabet) for _ in range(10))

        kce = Key(Constants.NOTEBOOK.label).eq(notebook)
        items = dynamo_table.query(KeyConditionExpression=kce, Limit=1)
        
        if items['Count'] == 0:

            password_hash = Authenticator.hash(data[Constants.PASSWORD.raw])

            r = dynamo_table.put_item(Item={
                Constants.NOTEBOOK.label: notebook,
                Constants.DATETIME.label: Constants.PASSWORD.label,
                Constants.PASSWORD.label: password_hash})

            print_dbg(json.dumps(r))

            break

    return json.dumps({Constants.NOTEBOOK.raw: notebook})


@app.delete("/journal/delete")
def journal_delete():
    data = request.json

    if Constants.NOTEBOOK.raw not in data:
        return 'Notebook key not supplied\n'

    notebook = data[Constants.NOTEBOOK.raw]
    query = boto3.dynamodb.conditions.Key(Constants.NOTEBOOK.label).eq(notebook)
    items = dynamo_table.query(KeyConditionExpression=query)['Items']

    print_dbg(json.dumps(items, indent=2))

    with dynamo_table.batch_writer() as bw:
        for item in items:
            key = {
                    Constants.NOTEBOOK.label: notebook,
                    Constants.DATETIME.label: item[Constants.DATETIME.label]
            }

            bw.delete_item(Key=key)

    return json.dumps({'deleted': f'{len(items)}'})


@app.post("/journal/log")
def journal_log():
    data = request.json

    if Constants.NOTEBOOK.raw not in data or Constants.MESSAGE.raw not in data:
        return json.dumps({'status': '300', 'error': 'Missing notebook id or message...\n'})

    print_dbg(data)

    item = {Constants.NOTEBOOK.label: data[Constants.NOTEBOOK.raw],
            Constants.DATETIME.label: str(datetime.now()),
            Constants.MESSAGE.label: data[Constants.MESSAGE.raw],
            Constants.PASSWORD.label: data[Constants.PASSWORD.raw],
           }

    for k in Constants.trans_dict.keys():
        if k not in item and k in data and data[k]:
            item[Constants.trans_dict[k]] = data[k]

    print_dbg(json.dumps(item))

    try:
        Authenticator.auth(
                dynamo_table,
                item[Constants.NOTEBOOK.label],
                item[Constants.PASSWORD.label])

    except KeyError:
        print_dbg(traceback.format_exc())
        return "403 Forbidden"

    except VerifyMismatchError:
        print_dbg(traceback.format_exc())
        return "403 Forbidden"
        # return "401 Unauthorized" # leaks information

    r = dynamo_table.put_item(Item=item)

    res = data
    res[Constants.DATETIME.raw] = item[Constants.DATETIME.label]

    return json.dumps(res)


@app.post("/journal/read")
def journal_read():
    try:
        data = request.json

        if Constants.NOTEBOOK.raw not in data:
            return 'Notebook key not supplied\n'

        notebook = data[Constants.NOTEBOOK.raw]
        dt = data[Constants.DATETIME.raw] if Constants.DATETIME.raw in data else None

        kce = Key(Constants.NOTEBOOK.label).eq(notebook)

        if dt:
            kce &= Key(Constants.DATETIME.label).begins_with(dt)

        fe = None

        optional = [
                Constants.AUTHOR.raw,
                Constants.TAG1.raw,
                Constants.TAG2.raw,
                Constants.TAG3.raw,
                Constants.TAG4.raw,
                ]

        for k in optional:
            if k in Constants.trans_dict and k in data:
                v = Constants.trans_dict[k]
                condition = Key(v).eq(data[k])
                fe = fe & condition if fe is not None else condition

        if fe:
            results = dynamo_table.query(KeyConditionExpression=kce, FilterExpression=fe)
        else:
            results = dynamo_table.query(KeyConditionExpression=kce)

        print_dbg("results:\n", json.dumps(results, indent=2))

        if 0 < results['Count']:
            d = results['Items'][0]
            l = [_ for _ in d.keys()]

            for e in l:

                if e in Constants.r_trans_dict:
                    new_k = Constants.r_trans_dict[e]
                    d[new_k] = d[e]
                    d.pop(e)

                elif e not in Constants.r_trans_dict.values():
                    d.pop(e)

        return json.dumps({'count': results['Count'], 'items': results['Items']})

    except Exception:
        print_dbg("request:\n", json.dumps(request.json, indent=2))
        print_dbg(traceback.format_exc())
        return "500 server error"
