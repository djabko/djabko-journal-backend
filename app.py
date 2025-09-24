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
        "update",
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


def http_to_json(message):
    a = message.split()
    return json.dumps({'status': a[0], 'message': ' '.join(a[1:])})

def dict_to_json(status, d):
    d['status'] = str(status)
    return json.dumps(d)

def extract_params(request, params, labels=False):
    data = request.json

    item = {}

    for i, e in enumerate(params):
        if e.raw in data:
            item[params[i].label] = data[params[i].raw]
        else:
            raise KeyError

    if labels:
        for k in Constants.trans_dict.keys():
            if k not in item and k in data and data[k]:
                item[Constants.trans_dict[k]] = data[k]

    return item


@app.route("/journal/")
def index():
    return json.dumps({"views": [cat(PREFIX, x) for x in VIEWS]})


@app.post("/journal/create")
def journal_create():

    while True:
        data = request.json

        if Constants.PASSWORD.raw not in data:
            return http_to_json('400 Missing Password')

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

    return dict_to_json(200, {Constants.NOTEBOOK.raw: notebook})


@app.delete("/journal/delete")
def journal_delete():
    data = request.json

    if Constants.NOTEBOOK.raw not in data \
            or Constants.PASSWORD.raw not in data:
        return http_to_json('400 Insufficient notebook parameters.')

    try:
        notebook = data[Constants.NOTEBOOK.raw]
        password = data[Constants.PASSWORD.raw]
        Authenticator.auth(dynamo_table, notebook, password)

    except KeyError:
        print_dbg(traceback.format_exc())
        return http_to_json("403 Forbidden")

    except VerifyMismatchError:
        print_dbg(traceback.format_exc())

        if DEBUG_MODE:
            return http_to_json("401 Unauthorized")
        else:
            return http_to_json("403 Forbidden")

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

    return dict_to_json(200, {'deleted': f'{len(items)}'})


@app.post("/journal/log")
def journal_log():
    data = request.json

    print_dbg(data)

    required = [Constants.NOTEBOOK,
                Constants.MESSAGE,
                Constants.PASSWORD]

    try:
        item = extract_params(request, required, labels=True)
    except KeyError:
        return http_to_json(f'400 Required parameters: {[e.raw for e in required]}...')

    item[Constants.DATETIME.label] = str(datetime.now())
    print_dbg(json.dumps(item))

    try:
        notebook = item[Constants.NOTEBOOK.label]
        password = item[Constants.PASSWORD.label]
        Authenticator.auth(dynamo_table, notebook, password)

    except KeyError:
        print_dbg(traceback.format_exc())
        return http_to_json("403 Forbidden")

    except VerifyMismatchError:
        print_dbg(traceback.format_exc())

        if DEBUG_MODE:
            return http_to_json("401 Unauthorized")
        else:
            return http_to_json("403 Forbidden")

    r = dynamo_table.put_item(Item=item)

    res = data
    res[Constants.DATETIME.raw] = item[Constants.DATETIME.label]

    return dict_to_json(200, res)


@app.post("/journal/read")
def journal_read():
    try:
        data = request.json

        if Constants.NOTEBOOK.raw not in data:
            return http_to_json('400 Notebook key not supplied')

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

        return dict_to_json(200, {'count': results['Count'], 'items': results['Items']})

    except Exception:
        print_dbg("request:\n", json.dumps(request.json, indent=2))
        print_dbg(traceback.format_exc())
        return http_to_json("500 server error")
