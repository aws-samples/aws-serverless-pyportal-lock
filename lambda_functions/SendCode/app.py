# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os
import json
import boto3
import random

pinpoint = boto3.client('pinpoint')
ssm = boto3.client('ssm')

applicationId = os.environ.get('APPLICATION_ID')
parameterName = os.environ.get('PARAMETER_NAME')
message = os.environ.get('MESSAGE')

def lambda_handler(event, context):
    print(event)
    body = json.loads(event['body'])

    number = "+1" + str(body['number'])
    code = str(random.randint(1111,9999))

    addresses = {}
    addresses[number] = {'ChannelType': 'SMS'}
    pinpoint.send_messages(
        ApplicationId=applicationId,
        MessageRequest={
            'Addresses': addresses,
            'MessageConfiguration': {
                'SMSMessage': {
                    'Body': message + code,
                    'MessageType': 'TRANSACTIONAL'
                }
            }
        }
    )

    state = { "locked": True, "code": code }

    response = ssm.put_parameter(
        Name=parameterName,
        Value=json.dumps(state),
        Type='String',
        Overwrite=True
    )

    return {
        "statusCode": 200,
        "body": json.dumps(state)
    }
