#!python


import os, boto3, json, secrets, string

from datetime import datetime
from flask import Flask, request, redirect
from boto3.dynamodb.conditions import Key


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

        kce = Key('Notebook').eq(notebook)
        items = dynamo_table.query(KeyConditionExpression=kce, Limit=1)
        
        if items['Count'] == 0:
            break

    return json.dumps({"notebook": notebook})


@app.delete("/journal/delete")
def journal_delete():
    data = request.json

    if 'notebook' not in data:
        return 'Notebook key not supplied\n'

    notebook = data['notebook']
    query = boto3.dynamodb.conditions.Key('Notebook').eq(notebook)
    items = dynamo_table.query(KeyConditionExpression=query)['Items']

    print(json.dumps(items, indent=2))

    with dynamo_table.batch_writer() as bw:
        for item in items:
            key = {'Notebook': notebook, 'Datetime': item['Datetime']}

            bw.delete_item(Key=key)

    return json.dumps({'deleted': f'{len(items)}'})

FIELD_TRANS_DICT = {
    'author': 'Author',
    'tag1': 'Tag 1',
    'tag2': 'Tag 2',
    'tag3': 'Tag 3',
    'tag4': 'Tag 4',
}


@app.post("/journal/log")
def journal_log():
    data = request.json

    if 'notebook' not in data or 'message' not in data:
        return json.dumps({'status': '300', 'error': 'Missing notebook id or message...\n'})

    print(data)

    item = {'Notebook': data['notebook'],
            'Datetime': str(datetime.now()),
            'Message':  data['message'],
           }

    for k in FIELD_TRANS_DICT.keys():
        if k in data and data[k]:
            item[FIELD_TRANS_DICT[k]] = data[k]

    print("\nWRITING\n")
    print(json.dumps(item))

    r = dynamo_table.put_item(Item=item)

    return json.dumps(item)


@app.post("/journal/read")
def journal_read():
    data = request.json

    if 'notebook' not in data:
        return 'Notebook key not supplied\n'

    notebook = data['notebook']
    dt = data['datetime'] if 'datetime' in data else None

    kce = Key('Notebook').eq(notebook)

    if dt:
        kce &= Key('Datetime').begins_with(dt)

    fe = None

    optional = {'author': 'Author', 'tag1': 'Tag 1', 'tag2': 'Tag 2', 'tag3': 'Tag 3', 'tag4': 'Tag 4'}

    for k,v in optional.items():
        if k in data:
            condition &= Key(v).begins_with(data[k])
            fe = condition if fe is None else fe & condition

    if fe:
        items = dynamo_table.query(KeyConditionExpression=kce, FilterExpression=fe)
    else:
        items = dynamo_table.query(KeyConditionExpression=kce)

    if len(items) <= 0:
        print('[]')

    print(json.dumps(items, indent=2))

    return json.dumps({'count': items['Count'], 'items': items['Items']})
