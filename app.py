#!python


import os, boto3, json, secrets, string

from datetime import datetime
from flask import Flask, request, redirect
from boto3.dynamodb.conditions import Key

from util import *


def get_priv(key):
    if key not in os.environ:
        print(f'ERROR: missing environment variable {key}')
        exit(-1)

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


def cat(prefix, suffix):
    return f'{prefix}-{suffix}'


@app.route("/journal/")
def index():
    return json.dumps({"views": [cat(PREFIX, x) for x in VIEWS]})


@app.post("/journal/create")
def journal_create():

    while True:
        alphabet = string.ascii_letters + string.digits
        notebook = ''

        for i in range(3):
            s = ''.join(secrets.choice(alphabet) for _ in range(10))
            notebook += s + '-'

        notebook += ''.join(secrets.choice(alphabet) for _ in range(10))

        kce = Key(Constants.NOTEBOOK.label).eq(notebook)
        items = dynamo_table.query(KeyConditionExpression=kce, Limit=1)
        
        if items['Count'] == 0:
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

    print(json.dumps(items, indent=2))

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

    print(data)

    item = {Constants.NOTEBOOK.label: data[Constants.NOTEBOOK.raw],
            Constants.DATETIME.label: str(datetime.now()),
            Constants.MESSAGE.label: data[Constants.MESSAGE.raw],
           }

    for k in Constants.trans_dict.keys():
        if k not in item and k in data and data[k]:
            item[Constants.trans_dict[k]] = data[k]

    print(json.dumps(item))

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
            items = dynamo_table.query(KeyConditionExpression=kce, FilterExpression=fe)
        else:
            items = dynamo_table.query(KeyConditionExpression=kce)

        if len(items) <= 0:
            print('[]')

        print(json.dumps(items, indent=2))

        return json.dumps({'count': items['Count'], 'items': items['Items']})

    except Exception as e:
        print(json.dumps(request.json, indent=2))
        print(e)
        return "500 server error"
