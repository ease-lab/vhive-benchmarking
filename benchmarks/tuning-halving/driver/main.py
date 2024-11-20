# MIT License
#
# Copyright (c) 2021 Michal Baczun and EASE lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys

from driver import Driver
import tracing

import logging as log
import pickle

LAMBDA = os.environ.get('IS_LAMBDA', 'no').lower() in ['true', 'yes', '1']

if LAMBDA:
    import boto3
    import json

if not LAMBDA:
    import helloworld_pb2_grpc
    import helloworld_pb2
    import tuning_pb2_grpc
    import tuning_pb2
    import destination as XDTdst
    import source as XDTsrc
    import utils as XDTutil

    import grpc
    from grpc_reflection.v1alpha import reflection
    import argparse
    import socket

    from concurrent import futures

    parser = argparse.ArgumentParser()
    parser.add_argument("-dockerCompose", "--dockerCompose",
        dest="dockerCompose", default=False, help="Env docker compose")
    parser.add_argument("-tAddr", "--tAddr", dest="tAddr",
        default="trainer.default.127.0.0.1.nip.io:80",
        help="trainer address")
    parser.add_argument("-sp", "--sp", dest="sp", default="80", help="serve port")
    parser.add_argument("-zipkin", "--zipkin", dest="zipkinURL",
        default="http://zipkin.istio-system.svc.cluster.local:9411/api/v2/spans",
        help="Zipkin endpoint url")

    args = parser.parse_args()

if tracing.IsTracingEnabled():
    tracing.initTracer("driver", url=args.zipkinURL)
    tracing.grpcInstrumentClient()
    tracing.grpcInstrumentServer()

INLINE = "INLINE"
S3 = "S3"
XDT = "XDT"

class GreeterServicer(helloworld_pb2_grpc.GreeterServicer):
    def __init__(self, XDTconfig=None):
        self.driver = Driver(XDTconfig)

    def train(self, arg: dict) -> dict:
        log.info("Invoke Trainer")
        channel = grpc.insecure_channel(args.tAddr)
        stub = tuning_pb2_grpc.TrainerStub(channel)

        resp = stub.Train(tuning_pb2.TrainRequest(
            dataset=b'',  # via S3/XDT only
            dataset_key="dataset_key",
            model_config=pickle.dumps(arg['model_config']),
            count=arg['count'],
            sample_rate=arg['sample_rate']
        ))

        return {
            'model_key': resp.model_key,
            'pred_key': resp.pred_key,
            'score': resp.score,
            'params': pickle.loads(resp.params),
        }

    # Driver code below
    def SayHello(self, request, context):
        log.info("Driver received a request")
        self.driver.drive({'trainerfn': self.train})
        return helloworld_pb2.HelloReply(message=self.driver.storageBackend.bucket)

class AWSLambdaDriver:
    def __init__(self, XDTconfig=None):
        self.driver = Driver()

    def train(self, arg: dict) -> dict:
        log.info("Invoke Trainer")
        trainerArgs = {
            'dataset_key': 'dataset_key',
            'model_config': json.dumps(arg['model_config']),
            'count': arg['count'],
            'sample_rate': str(arg['sample_rate'])
        }
        resp = boto3.client("lambda").invoke(
            FunctionName = os.environ.get('TRAINER_FUNCTION'),
            InvocationType = 'RequestResponse',
            LogType = 'None',
            Payload = json.dumps(trainerArgs),
        )
        payloadBytes = resp['Payload'].read()
        payloadJson = json.loads(payloadBytes)

        return {
            'model_key': payloadJson['model_key'],
            'pred_key': payloadJson['pred_key'],
            'score': float(payloadJson['score']),
            'params': json.loads(payloadJson['params'])
        }

    def SayHello(self, event, context):
        log.info("Driver received a request")
        self.driver.drive({'trainerfn': self.train})
        return self.driver.storageBackend.bucket

def serve():
    transferType = os.getenv('TRANSFER_TYPE', S3)
    if transferType == S3:
        log.info("Using inline or s3 transfers")
        max_workers = int(os.getenv("MAX_SERVER_THREADS", 10))
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        helloworld_pb2_grpc.add_GreeterServicer_to_server(
            GreeterServicer(), server)
        SERVICE_NAMES = (
            helloworld_pb2.DESCRIPTOR.services_by_name['Greeter'].full_name,
            reflection.SERVICE_NAME,
        )
        reflection.enable_server_reflection(SERVICE_NAMES, server)
        server.add_insecure_port('[::]:' + args.sp)
        server.start()
        server.wait_for_termination()
    elif transferType == XDT:
        log.fatal("XDT not yet supported")
        XDTconfig = XDTutil.loadConfig()
    else:
        log.fatal("Invalid Transfer type")

def lambda_handler(event, context):
    awsLambdaDriver = AWSLambdaDriver()
    return awsLambdaDriver.SayHello(event, context)

if not LAMBDA and __name__ == '__main__':
    log.basicConfig(level=log.INFO)
    serve()
